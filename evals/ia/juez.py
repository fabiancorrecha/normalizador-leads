#!/usr/bin/env python3
"""Juez LLM: puntúa de 1 a 5 la calidad subjetiva de cada salida según una rúbrica.

Mide; no bloquea (lo que bloquea son los casos críticos de evaluar.py). Antes de fiarte de él,
calíbralo con notas humanas: si no se parece a ellas, sus números no significan nada.

Uso: juez.py prompts/<f>/vN.md [--modelo claude-opus-5-5] [--reutilizar] [--simulado RUTA]
     juez.py prompts/<f>/vN.md --calibrar [prompts/<f>/humanas.jsonl]

Puntúa las salidas de prompts/<f>/resultados/vN.jsonl y escribe vN.juez.jsonl a su lado.
Rúbrica: prompts/<f>/rubrica.md si existe; si no, evals/ia/rubrica_juez.md. Los criterios son su
lista numerada (1. **Fidelidad**: …).
humanas.jsonl: {"id", "repeticion" (1 si falta), y una nota de 1 a 5 por criterio}, con la nota de
consenso de las personas expertas. Calibrado = al menos 10 respuestas y kappa ponderada cuadrática
>= 0.6 en cada criterio. El resultado se guarda en prompts/<f>/resultados/calibracion.json.
"""

import argparse
import concurrent.futures
import datetime
import json
import pathlib
import re
import sys
import unicodedata

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from comun import (
    RUBRICA,
    coste_usd,
    escribir_jsonl,
    huella,
    leer_jsonl,
    relativa,
    ruta_casos,
    ruta_resultados,
)

KAPPA_MINIMA = 0.6
MUESTRA_MINIMA = 10


def criterios_de(rubrica: str) -> list[str]:
    sin_comentarios = re.sub(r"<!--.*?-->", "", rubrica, flags=re.DOTALL)
    nombres = re.findall(r"^\s*\d+\.\s+\*\*([^*]+)\*\*", sin_comentarios, re.MULTILINE)
    sin_tildes = (
        unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode()
        for n in nombres
    )
    return [re.sub(r"\W", "", n.split()[0]).lower() for n in sin_tildes]


def kappa_cuadratica(
    a: list[int], b: list[int], minimo: int = 1, maximo: int = 5
) -> float:
    """Kappa de Cohen con pesos cuadráticos: 1 = acuerdo perfecto, 0 = el del azar."""
    k = maximo - minimo + 1
    n = len(a)
    observada = [[0] * k for _ in range(k)]
    for x, y in zip(a, b):
        observada[x - minimo][y - minimo] += 1
    fila = [sum(observada[i]) for i in range(k)]
    columna = [sum(observada[i][j] for i in range(k)) for j in range(k)]
    desacuerdo = esperado = 0.0
    for i in range(k):
        for j in range(k):
            peso = (i - j) ** 2 / (k - 1) ** 2
            desacuerdo += peso * observada[i][j]
            esperado += peso * fila[i] * columna[j] / n
    return 1.0 if esperado == 0 else 1 - desacuerdo / esperado


def calibrar(
    humanas: list[dict], juez: list[dict], criterios: list[str]
) -> tuple[dict[str, float], int]:
    notas_juez = {
        (f["id"], f.get("repeticion", 1)): f for f in juez if not f.get("omitida")
    }
    pares = [
        (h, notas_juez[(h["id"], h.get("repeticion", 1))])
        for h in humanas
        if (h["id"], h.get("repeticion", 1)) in notas_juez
    ]
    kappas = {
        c: kappa_cuadratica(
            [int(h[c]) for h, _ in pares], [int(j[c]) for _, j in pares]
        )
        for c in criterios
        if pares
    }
    return kappas, len(pares)


def modelo_puntuacion(criterios: list[str]):
    from typing import Literal

    from pydantic import Field, create_model

    nota = Literal[1, 2, 3, 4, 5]
    return create_model(
        "Puntuacion",
        justificacion=(
            str,
            Field(description="Una o dos frases que citan la respuesta."),
        ),
        **{c: (nota, ...) for c in criterios},
    )


def puntuar(
    cliente, modelo: str, rubrica: str, esquema, caso: dict, fila: dict
) -> dict:
    r = cliente.messages.parse(
        model=modelo,
        max_tokens=16000,
        system=rubrica,
        messages=[
            {
                "role": "user",
                "content": (
                    f"<entrada>\n{caso.get('entrada', '')}\n</entrada>\n<respuesta>\n{fila.get('salida', '')}\n"
                    "</respuesta>\nPuntúa la respuesta con la rúbrica. Justifica antes de puntuar."
                ),
            }
        ],
        output_format=esquema,
        output_config={"effort": "medium"},
    )
    if r.stop_reason == "refusal" or r.parsed_output is None:
        return {"omitida": f"el juez no puntuó (stop_reason={r.stop_reason})"}
    u = r.usage
    return r.parsed_output.model_dump() | {
        "modelo_juez": r.model,
        "coste_usd": coste_usd(r.model, u.input_tokens, u.output_tokens),
    }


def es_fatal(e: Exception) -> bool:
    """Errores que se repetirían en todas las llamadas: credenciales, modelo o petición inválidos."""
    return "authentication" in str(e).lower() or type(e).__name__ in (
        "AuthenticationError",
        "PermissionDeniedError",
        "BadRequestError",
        "NotFoundError",
    )


def simulador(ruta: pathlib.Path, version: str):
    if ruta.is_dir():
        ruta = ruta / f"{version}.juez.jsonl"
    notas = {(f["id"], f.get("repeticion", 1)): f for f in leer_jsonl(ruta)}

    def puntuar_simulado(caso: dict, fila: dict) -> dict:
        nota = notas.get((fila["id"], fila.get("repeticion", 1))) or notas.get(
            (fila["id"], 1)
        )
        if not nota:
            return {"omitida": f"{relativa(ruta)} no tiene nota para este caso"}
        return {k: v for k, v in nota.items() if k not in ("id", "repeticion")} | {
            "modelo_juez": "simulado",
            "coste_usd": 0.0,
        }

    return puntuar_simulado


def main() -> int:
    ap = argparse.ArgumentParser(description="Juez LLM con calibración.")
    ap.add_argument("prompt", help="prompts/<f>/vN.md (sus salidas ya generadas)")
    ap.add_argument("--modelo", default="claude-opus-5-5")
    ap.add_argument("--reutilizar", action="store_true")
    ap.add_argument("--simulado", metavar="RUTA")
    ap.add_argument("--calibrar", nargs="?", const="", metavar="HUMANAS")
    ap.add_argument("--concurrencia", type=int, default=4)
    args = ap.parse_args()

    prompt = pathlib.Path(args.prompt)
    salidas, destino = ruta_resultados(prompt), ruta_resultados(prompt, ".juez")
    ruta_rubrica = (
        prompt.parent / "rubrica.md"
        if (prompt.parent / "rubrica.md").exists()
        else RUBRICA
    )
    try:
        filas = leer_jsonl(salidas)
        casos = {c["id"]: c for c in leer_jsonl(ruta_casos(prompt))}
        rubrica = ruta_rubrica.read_text(encoding="utf-8")
    except OSError as e:
        print(
            f"❌ {e}  (¿generaste las salidas con evals/ia/generar.py {args.prompt}?)"
        )
        return 2
    criterios = criterios_de(rubrica)
    if not criterios:
        print(
            f"❌ {relativa(ruta_rubrica)} no tiene criterios numerados (1. **Nombre**: …)."
        )
        return 2

    modo = "simulado" if args.simulado else args.modelo
    firma = huella(salidas.read_text(encoding="utf-8"), rubrica, modo)
    previas = leer_jsonl(destino) if args.reutilizar and destino.exists() else []
    if previas and {f.get("huella") for f in previas} == {firma}:
        notas = previas
        print(
            f"↺ {relativa(destino)} ya puntúa estas salidas con esta rúbrica: se reutiliza."
        )
    else:
        if args.simulado:
            hacer = simulador(pathlib.Path(args.simulado), prompt.stem)
        else:
            try:
                import anthropic

                esquema = modelo_puntuacion(criterios)
            except ImportError:
                print(
                    "❌ Faltan dependencias: pip install anthropic pydantic   (o prueba con --simulado)"
                )
                return 2
            cliente = anthropic.Anthropic(max_retries=4)

            para_el_juez = re.sub(
                r"<!--.*?-->", "", rubrica, flags=re.DOTALL
            ).strip()  # las notas para personas, fuera

            def hacer(caso: dict, fila: dict) -> dict:
                return puntuar(cliente, args.modelo, para_el_juez, esquema, caso, fila)

        def una(fila: dict) -> dict:
            base = {
                "id": fila["id"],
                "repeticion": fila.get("repeticion", 1),
                "huella": firma,
            }
            if fila.get("error") or not str(fila.get("salida") or "").strip():
                return base | {"omitida": "sin salida que puntuar"}
            try:
                return base | hacer(casos.get(fila["id"], {}), fila)
            except Exception as e:
                if es_fatal(e):
                    raise
                return base | {"omitida": f"{type(e).__name__}: {e}"[:300]}

        print(
            f"Juez ({'simulado' if args.simulado else args.modelo}) sobre {len(filas)} salidas · "
            f"rúbrica {relativa(ruta_rubrica)}…"
        )
        try:
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=max(1, args.concurrencia)
            ) as pool:
                notas = list(pool.map(una, filas))
        except Exception as e:
            if not es_fatal(e):
                raise
            print(
                "❌ No hay credenciales para la API de Anthropic (ANTHROPIC_API_KEY o `ant auth login`)."
                if "authentication" in str(e).lower()
                or "Authentication" in type(e).__name__
                else f"❌ La API rechaza la petición del juez: {e}"
            )
            return 2
        escribir_jsonl(destino, notas)

    puntuadas = [n for n in notas if not n.get("omitida")]
    if puntuadas:
        medias = " · ".join(
            f"{c} {sum(int(n[c]) for n in puntuadas) / len(puntuadas):.1f}"
            for c in criterios
        )
        print(f"Medias (1-5) sobre {len(puntuadas)} salidas: {medias}")
        for n in sorted(puntuadas, key=lambda n: min(int(n[c]) for c in criterios))[:3]:
            peor = min(criterios, key=lambda c: int(n[c]))
            if int(n[peor]) <= 3:
                print(
                    f"  Revisa {n['id']}#{n['repeticion']}: {peor} {n[peor]} — {n.get('justificacion', '')[:160]}"
                )
    if len(puntuadas) < len(notas):
        print(
            f"⚠ {len(notas) - len(puntuadas)} salidas sin puntuar (sin salida o error del juez)."
        )

    ruta_calibracion = prompt.parent / "resultados" / "calibracion.json"
    huella_juez = huella(rubrica, modo)
    if args.calibrar is None:
        previa = (
            json.loads(ruta_calibracion.read_text())
            if ruta_calibracion.exists()
            else {}
        )
        if previa.get("huella_juez") == huella_juez and previa.get("apto"):
            print(
                f"Juez calibrado el {previa['fecha']}: kappa mínima {min(previa['kappas'].values()):.2f} "
                f"con {previa['n']} respuestas."
            )
        else:
            print(
                "⚠ Juez sin calibrar para esta rúbrica y modelo: no te fíes de estas medias hasta pasar "
                f"--calibrar (kappa >= {KAPPA_MINIMA} con al menos {MUESTRA_MINIMA} notas humanas)."
            )
        return 0

    ruta_humanas = (
        pathlib.Path(args.calibrar)
        if args.calibrar
        else prompt.parent / "humanas.jsonl"
    )
    try:
        humanas = leer_jsonl(ruta_humanas)
    except OSError:
        print(f"❌ No encuentro las notas humanas en {relativa(ruta_humanas)}.")
        return 1
    invalidas = [
        f"{h.get('id')}.{c}"
        for h in humanas
        for c in criterios
        if h.get(c) not in (1, 2, 3, 4, 5)
    ]
    if invalidas:
        print(
            f"❌ {relativa(ruta_humanas)}: cada criterio necesita una nota entera de 1 a 5 "
            f"(revisa {', '.join(invalidas[:5])})."
        )
        return 1
    kappas, n = calibrar(humanas, puntuadas, criterios)
    print(f"\nCalibración contra {n} notas humanas ({relativa(ruta_humanas)}):")
    for c, k in kappas.items():
        print(f"  {c}: kappa {k:.2f} {'✅' if k >= KAPPA_MINIMA else '❌'}")
    apto = n >= MUESTRA_MINIMA and all(k >= KAPPA_MINIMA for k in kappas.values())
    if n < MUESTRA_MINIMA:
        print(
            f"  ❌ Solo {n} respuestas emparejadas: hacen falta al menos {MUESTRA_MINIMA} (mejor 30-50)."
        )
    ruta_calibracion.write_text(
        json.dumps(
            {
                "fecha": datetime.datetime.now(datetime.timezone.utc)
                .date()
                .isoformat(),
                "modelo_juez": modo,
                "huella_juez": huella_juez,
                "n": n,
                "kappas": {c: round(k, 3) for c, k in kappas.items()},
                "apto": apto,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        f"CALIBRACIÓN: {'✅ el juez se parece a las personas' if apto else '❌ no te fíes de este juez todavía'}"
    )
    return 0 if apto else 1


if __name__ == "__main__":
    sys.exit(main())
