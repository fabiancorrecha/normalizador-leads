#!/usr/bin/env python3
"""Genera las salidas de una versión de prompt sobre sus casos, con varias repeticiones.

Uso: generar.py prompts/<funcionalidad>/vN.md [--repeticiones 3] [--concurrencia 4]
                [--reutilizar] [--simulado RUTA] [--salida RUTA]

Escribe una fila por caso y repetición en prompts/<funcionalidad>/resultados/vN.jsonl con: id,
repeticion, salida, modelo_pedido, modelo_respuesta, fallback, stop_reason, tokens, coste_usd,
latencia_s (y "error" si la llamada falló). El modelo no es determinista: las repeticiones muestran
qué casos fallan solo a veces.

Cada llamada cuesta dinero: se lanza a mano o en CI cuando cambia un prompt, nunca en `make check`.
--reutilizar   no vuelve a pagar si ya hay resultados del mismo prompt, casos y repeticiones.
--simulado     lee salidas fijas de un JSONL ({"id", "salida"}) o de RUTA/vN.jsonl si es una carpeta,
               sin API ni coste. Si un id se repite, cada repetición usa la siguiente línea.
"""

import argparse
import concurrent.futures
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from comun import (
    coste_usd,
    escribir_jsonl,
    huella,
    leer_jsonl,
    leer_prompt,
    relativa,
    renderizar,
    ruta_casos,
    ruta_resultados,
)

BETA_FALLBACKS = (
    "server-side-fallback-2026-07-01"  # la que corresponde a fallbacks="default"
)
SIN_FALLBACK = {"claude-haiku-5-5"}  # la API no tiene fallback para estos modelos
ESFUERZOS = {"low", "medium", "high", "xhigh", "max"}


class Fatal(Exception):
    """Un error que se repetiría en todas las llamadas: se para en vez de gastar en vano."""


def peticion(prompt: dict, caso: dict) -> dict:
    p = {
        "model": prompt["modelo"],
        "max_tokens": int(prompt.get("max_tokens") or 16000),
        "messages": [{"role": "user", "content": renderizar(prompt["usuario"], caso)}],
    }
    if prompt.get("sistema"):
        p["system"] = renderizar(prompt["sistema"], caso)
    config = {}
    if prompt.get("esfuerzo"):
        config["effort"] = prompt["esfuerzo"]
    # salida estructurada: la API garantiza JSON válido según el esquema
    if prompt.get("esquema"):
        esquema = pathlib.Path(prompt["ruta"]).parent / prompt["esquema"]
        config["format"] = {
            "type": "json_schema",
            "schema": json.loads(esquema.read_text(encoding="utf-8")),
        }
    if config:
        p["output_config"] = config
    return p


def llamar(cliente, prompt: dict, caso: dict) -> dict:
    import anthropic

    p = peticion(prompt, caso)
    con_fallback = (
        prompt.get("fallbacks", "no") == "default" and p["model"] not in SIN_FALLBACK
    )
    inicio = time.monotonic()
    try:
        # si el modelo se niega por seguridad, la API reintenta con el recomendado
        if con_fallback:
            flujo = cliente.beta.messages.stream(
                betas=[BETA_FALLBACKS], fallbacks="default", **p
            )
        else:
            flujo = cliente.messages.stream(**p)
        with flujo as stream:
            r = stream.get_final_message()
    except TypeError as e:
        if "authentication" in str(e).lower():
            raise Fatal("sin credenciales") from e
        raise
    except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as e:
        raise Fatal("sin credenciales") from e
    except (anthropic.BadRequestError, anthropic.NotFoundError) as e:
        raise Fatal(
            f"la API rechaza la petición: revisa la cabecera del prompt ({e})"
        ) from e
    except (
        anthropic.APIError
    ) as e:  # tras los reintentos del SDK: se anota y se sigue con el resto
        return {
            "error": f"{type(e).__name__}: {e}"[:400],
            "latencia_s": round(time.monotonic() - inicio, 3),
        }

    u = r.usage
    escritura = getattr(u, "cache_creation_input_tokens", 0) or 0
    lectura = getattr(u, "cache_read_input_tokens", 0) or 0
    fila = {
        "modelo_respuesta": r.model,
        "fallback": any(
            getattr(i, "type", "") == "fallback_message"
            for i in (getattr(u, "iterations", None) or [])
        ),
        "stop_reason": r.stop_reason,
        # Con una negativa el texto parcial no vale: se descarta.
        "salida": ""
        if r.stop_reason == "refusal"
        else "".join(b.text for b in r.content if b.type == "text"),
        "tokens_entrada": u.input_tokens + escritura + lectura,
        "tokens_salida": u.output_tokens,
        "coste_usd": coste_usd(
            r.model, u.input_tokens, u.output_tokens, escritura, lectura
        ),
        "latencia_s": round(time.monotonic() - inicio, 3),
    }
    if r.stop_reason == "refusal" and getattr(r, "stop_details", None):
        fila["categoria_negativa"] = getattr(r.stop_details, "category", None)
    return fila


def simulador(ruta: pathlib.Path, prompt: dict):
    if ruta.is_dir():
        ruta = ruta / f"{prompt['version']}.jsonl"
    por_id: dict[str, list[dict]] = {}
    for fila in leer_jsonl(ruta):
        por_id.setdefault(fila["id"], []).append(fila)

    def llamar_simulado(caso: dict, repeticion: int) -> dict:
        opciones = por_id.get(caso["id"])
        if not opciones:
            return {"error": f"{relativa(ruta)} no tiene salida para este caso"}
        f = opciones[(repeticion - 1) % len(opciones)]
        return {
            "modelo_respuesta": "simulado",
            "fallback": False,
            "stop_reason": f.get("stop_reason", "end_turn"),
            "salida": f.get("salida", ""),
            "tokens_entrada": 0,
            "tokens_salida": 0,
            "coste_usd": 0.0,
            "latencia_s": 0.0,
        }

    return llamar_simulado


SIN_CREDENCIALES = """❌ No hay credenciales para la API de Anthropic.
   Define ANTHROPIC_API_KEY (en CI, como secreto del repositorio) o inicia sesión con `ant auth login`.
   Para probar el circuito sin coste: --simulado prompts/<funcionalidad>/simulado"""


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Genera las salidas de una versión de prompt."
    )
    ap.add_argument("prompt")
    ap.add_argument("--casos", help="por defecto, casos.jsonl junto al prompt")
    ap.add_argument("--repeticiones", type=int, default=3)
    ap.add_argument("--concurrencia", type=int, default=4)
    ap.add_argument("--reutilizar", action="store_true")
    ap.add_argument("--simulado", metavar="RUTA")
    ap.add_argument("--salida", metavar="RUTA")
    args = ap.parse_args()

    try:
        prompt = leer_prompt(args.prompt)
        ruta_c = pathlib.Path(args.casos) if args.casos else ruta_casos(args.prompt)
        casos = leer_jsonl(ruta_c)
        for caso in casos:
            # una plantilla que pide un campo que el caso no tiene falla aquí, gratis
            peticion(prompt, caso)
    except (OSError, ValueError, KeyError) as e:
        print(f"❌ {e}")
        return 2
    if not casos:
        print(
            f"❌ No hay casos en {relativa(ruta_c)}: un eval sin casos no demuestra nada."
        )
        return 2
    if prompt.get("esfuerzo") and prompt["esfuerzo"] not in ESFUERZOS:
        print(
            f"❌ esfuerzo «{prompt['esfuerzo']}» no válido: {', '.join(sorted(ESFUERZOS))}"
        )
        return 2

    destino = pathlib.Path(args.salida) if args.salida else ruta_resultados(args.prompt)
    modo = "simulado" if args.simulado else "api"
    firma = huella(
        pathlib.Path(args.prompt).read_text(encoding="utf-8"),
        ruta_c.read_text(encoding="utf-8"),
    )
    previas = leer_jsonl(destino) if args.reutilizar and destino.exists() else []
    if (
        previas
        and {(f.get("huella"), f.get("modo")) for f in previas} == {(firma, modo)}
        and max(f.get("repeticion", 1) for f in previas) == args.repeticiones
    ):
        print(
            f"↺ {relativa(destino)} ya es de este prompt, casos y repeticiones: se reutiliza."
        )
        return 0

    if args.simulado:
        hacer = simulador(pathlib.Path(args.simulado), prompt)
    else:
        try:
            import anthropic
        except ImportError:
            print(
                "❌ Falta el SDK de Anthropic: pip install anthropic   (o prueba con --simulado)"
            )
            return 2
        cliente = anthropic.Anthropic(max_retries=4)

        def hacer(caso: dict, repeticion: int) -> dict:
            return llamar(cliente, prompt, caso)

    trabajos = [(caso, n) for caso in casos for n in range(1, args.repeticiones + 1)]
    print(
        f"{prompt['nombre']}/{prompt['version']}: {len(trabajos)} llamadas ({len(casos)} casos × "
        f"{args.repeticiones} repeticiones) a {'salidas simuladas' if args.simulado else prompt['modelo']}…"
    )
    filas = {}
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=max(1, args.concurrencia)
    ) as pool:
        futuros = {pool.submit(hacer, caso, n): (caso, n) for caso, n in trabajos}
        try:
            for futuro in concurrent.futures.as_completed(futuros):
                caso, n = futuros[futuro]
                filas[(caso["id"], n)] = {
                    "id": caso["id"],
                    "repeticion": n,
                    "prompt": f"{prompt['nombre']}/{prompt['version']}",
                    "modelo_pedido": prompt["modelo"],
                    "huella": firma,
                    "modo": modo,
                } | futuro.result()
        except Fatal as e:
            pool.shutdown(wait=False, cancel_futures=True)
            print(SIN_CREDENCIALES if str(e) == "sin credenciales" else f"❌ {e}")
            return 2

    ordenadas = [filas[(caso["id"], n)] for caso, n in trabajos]
    escribir_jsonl(destino, ordenadas)
    errores = sum(1 for f in ordenadas if f.get("error"))
    coste = sum(f.get("coste_usd") or 0 for f in ordenadas)
    print(
        f"→ {relativa(destino)} · coste estimado ${coste:.4f}"
        + (f" · ⚠ {errores} errores" if errores else "")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
