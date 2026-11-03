#!/usr/bin/env python3
"""Evalúa las salidas de una versión de prompt contra sus casos y, si se pide, contra la versión anterior.

Uso: evaluar.py prompts/<f>/vN.md [--base prompts/<f>/vN-1.md] [--umbral 0.9]
     evaluar.py salidas.jsonl --casos casos.jsonl [--base salidas_base.jsonl]

casos.jsonl: {"id", "entrada", "critico": bool, "requisitos": ["REQ-…"] (opcional), y las comprobaciones:
  "debe_incluir": [...], "no_debe_incluir": [...]       subcadenas, sin distinguir mayúsculas
  "debe_coincidir": [...], "no_debe_coincidir": [...]   expresiones regulares
  "campos": {"ruta.al.campo": valor}                    la salida es JSON (prompt con `esquema:`)}
salidas: las escribe generar.py, una fila por caso y repetición (también vale {"id", "salida"}).

Gate: 0 fallos críticos (un caso crítico falla si falla CUALQUIER repetición), tasa de aprobadas
>= umbral y, con --base, ninguna regresión (un caso que pasaba siempre y ahora falla alguna vez).
La calidad subjetiva va aparte, con el juez calibrado (juez.py): mide, no bloquea.
"""

import argparse
import json
import pathlib
import re
import sys
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from comun import (
    ROOT,
    es_prompt,
    huella,
    leer_jsonl,
    percentil,
    relativa,
    ruta_casos,
    ruta_resultados,
)


def valor_en(datos, ruta: str):
    for parte in ruta.split("."):
        if isinstance(datos, list) and parte.isdigit() and int(parte) < len(datos):
            datos = datos[int(parte)]
        elif isinstance(datos, dict) and parte in datos:
            datos = datos[parte]
        else:
            raise KeyError(ruta)
    return datos


def fallos_de(caso: dict, fila: dict) -> list[str]:
    if fila.get("error"):
        return [f"error: {fila['error']}"]
    if fila.get("stop_reason") == "refusal":
        return ["el modelo se negó a responder (refusal)"]
    if fila.get("stop_reason") == "max_tokens":
        return ["salida cortada por max_tokens"]
    original = str(fila.get("salida") or "")
    salida = original.lower()
    if not salida.strip():
        return ["sin salida"]
    fallos = [
        f"falta «{t}»" for t in caso.get("debe_incluir", []) if t.lower() not in salida
    ]
    fallos += [
        f"contiene «{t}»"
        for t in caso.get("no_debe_incluir", [])
        if t.lower() in salida
    ]
    fallos += [
        f"no coincide con /{p}/"
        for p in caso.get("debe_coincidir", [])
        if not re.search(p, original, re.IGNORECASE)
    ]
    fallos += [
        f"coincide con /{p}/"
        for p in caso.get("no_debe_coincidir", [])
        if re.search(p, original, re.IGNORECASE)
    ]
    if caso.get("campos"):
        try:
            datos = json.loads(re.sub(r"^\s*```(json)?\s*|\s*```\s*$", "", original))
        except json.JSONDecodeError:
            return fallos + ["la salida no es JSON"]
        for ruta, esperado in caso["campos"].items():
            try:
                obtenido = valor_en(datos, ruta)
            except KeyError:
                fallos.append(f"falta el campo «{ruta}»")
                continue
            if obtenido != esperado:
                fallos.append(
                    f"«{ruta}» = {json.dumps(obtenido, ensure_ascii=False)} (esperado "
                    f"{json.dumps(esperado, ensure_ascii=False)})"
                )
    return fallos


def por_caso(casos: list[dict], filas: list[dict]) -> dict[str, dict]:
    agrupadas: dict[str, list[dict]] = {}
    for fila in filas:
        agrupadas.setdefault(fila["id"], []).append(fila)
    resultado = {}
    for caso in casos:
        repeticiones = agrupadas.get(caso["id"]) or [{"id": caso["id"], "salida": ""}]
        fallos = [fallos_de(caso, f) for f in repeticiones]
        resultado[caso["id"]] = {
            "n": len(repeticiones),
            "k": sum(1 for f in fallos if not f),
            "fallos": Counter(m for f in fallos for m in f),
            "critico": bool(caso.get("critico")),
        }
    return resultado


def metricas(filas: list[dict]) -> dict:
    latencias = [
        f["latencia_s"] for f in filas if isinstance(f.get("latencia_s"), (int, float))
    ]
    costes = [f.get("coste_usd") for f in filas if "coste_usd" in f]
    return {
        "coste": sum(c for c in costes if c is not None),
        "coste_desconocido": sum(1 for c in costes if c is None),
        "p50": percentil(latencias, 0.5),
        "p95": percentil(latencias, 0.95),
        "tokens_entrada": sum(f.get("tokens_entrada") or 0 for f in filas),
        "tokens_salida": sum(f.get("tokens_salida") or 0 for f in filas),
        "fallbacks": sum(1 for f in filas if f.get("fallback")),
        "negativas": sum(1 for f in filas if f.get("stop_reason") == "refusal"),
        "cortadas": sum(1 for f in filas if f.get("stop_reason") == "max_tokens"),
        "errores": sum(1 for f in filas if f.get("error")),
        "con_metricas": bool(latencias),
    }


def tasa(resultado: dict) -> float:
    n = sum(r["n"] for r in resultado.values())
    return sum(r["k"] for r in resultado.values()) / n if n else 0.0


def resolver(ruta: str, que: str) -> pathlib.Path:
    if es_prompt(ruta):
        destino = ruta_resultados(ruta)
        if not destino.exists():
            raise FileNotFoundError(
                f"No hay resultados de {que} {ruta}: genéralos con "
                f"python3 evals/ia/generar.py {ruta}"
            )
        return destino
    return pathlib.Path(ruta)


def main() -> int:
    ap = argparse.ArgumentParser(description="Evalúa las salidas de un prompt.")
    ap.add_argument("salidas", help="prompts/<f>/vN.md o un JSONL de salidas")
    ap.add_argument("--casos")
    ap.add_argument(
        "--base", help="versión anterior (prompts/<f>/vN-1.md) o su JSONL de salidas"
    )
    ap.add_argument("--umbral", type=float, default=0.9)
    args = ap.parse_args()

    try:
        ruta_salidas = resolver(args.salidas, "la versión")
        if args.casos:
            ruta_c = pathlib.Path(args.casos)
        elif es_prompt(args.salidas):
            ruta_c = ruta_casos(args.salidas)
        else:  # prompts/<f>/resultados/vN.jsonl → prompts/<f>/casos.jsonl
            ruta_c = ruta_salidas.resolve().parent.parent / "casos.jsonl"
            # dónde estaban en el kit 1.x
            antigua = ROOT / "evals" / "ia" / "casos.jsonl"
            if not ruta_c.exists() and antigua.exists():
                print(
                    "⚠ Uso evals/ia/casos.jsonl (formato 1.x): muévelo a prompts/<funcionalidad>/casos.jsonl.\n"
                )
                ruta_c = antigua
        casos = leer_jsonl(ruta_c)
        filas = leer_jsonl(ruta_salidas)
        filas_base = leer_jsonl(resolver(args.base, "la base")) if args.base else None
    except (OSError, ValueError) as e:
        print(f"❌ {e}")
        return 1
    if not casos:
        print(
            f"❌ No hay casos en {relativa(ruta_c)}: un eval sin casos no demuestra nada."
        )
        return 1

    simuladas = any(f.get("modo") == "simulado" for f in filas)
    if simuladas:
        print("⚠ SALIDAS SIMULADAS: esto prueba el circuito, no el modelo.\n")
    desactualizadas = False
    if es_prompt(args.salidas):
        actual = huella(
            pathlib.Path(args.salidas).read_text(encoding="utf-8"),
            ruta_c.read_text(encoding="utf-8"),
        )
        desactualizadas = any(f.get("huella") not in (None, actual) for f in filas)

    resultado = por_caso(casos, filas)
    for caso in casos:
        r = resultado[caso["id"]]
        etiqueta = " [CRÍTICO]" if r["critico"] else ""
        if r["k"] == r["n"]:
            estado = f"✅ {r['k']}/{r['n']}"
        else:  # en un caso crítico, fallar una sola vez ya es un fallo
            marca = "⚠ inestable" if r["k"] and not r["critico"] else "❌"
            detalle = "; ".join(
                f"{m} ({c}/{r['n']})" for m, c in r["fallos"].most_common(3)
            )
            estado = f"{marca} {r['k']}/{r['n']} · {detalle}"
        print(f"{caso['id']}{etiqueta}: {estado}")

    criticos = [i for i, r in resultado.items() if r["critico"] and r["k"] < r["n"]]
    inestables = [i for i, r in resultado.items() if 0 < r["k"] < r["n"]]
    total_n = sum(r["n"] for r in resultado.values())
    t = tasa(resultado)
    print(
        f"\nAprobadas: {sum(r['k'] for r in resultado.values())}/{total_n} repeticiones ({t:.0%}, umbral "
        f"{args.umbral:.0%}) · Fallos críticos: {len(criticos)} · Inestables: {len(inestables)}"
    )
    m = metricas(filas)
    if m["con_metricas"] and not simuladas:
        desconocido = (
            f" (+{m['coste_desconocido']} llamadas sin precio en la tabla)"
            if m["coste_desconocido"]
            else ""
        )
        print(
            f"Coste: ${m['coste']:.4f}{desconocido} · Latencia p50 {m['p50']:.2f} s · p95 {m['p95']:.2f} s · "
            f"Tokens: {m['tokens_entrada']} entrada / {m['tokens_salida']} salida"
        )
        print(
            f"Fallbacks: {m['fallbacks']} · Negativas: {m['negativas']} · Cortadas: {m['cortadas']} · "
            f"Errores: {m['errores']}"
        )

    regresiones = []
    if filas_base is not None:
        base = por_caso(casos, filas_base)
        regresiones = [
            i
            for i in resultado
            if i in base and base[i]["k"] == base[i]["n"] > resultado[i]["k"]
        ]
        mejoras = [
            i
            for i in resultado
            if i in base and base[i]["k"] < base[i]["n"] == resultado[i]["k"]
        ]
        print(f"\nComparación con la base ({args.base}):")
        for nombre, ids in (
            ("Regresiones (pasaba siempre y ahora falla)", regresiones),
            ("Mejoras", mejoras),
        ):
            lista = ", ".join(
                f"{i} ({base[i]['k']}/{base[i]['n']} → {resultado[i]['k']}/{resultado[i]['n']})"
                for i in ids
            )
            print(f"  {nombre}: {lista or 'ninguna'}")
        mb = metricas(filas_base)
        linea = f"  Tasa: {tasa(base):.0%} → {t:.0%}"
        if m["con_metricas"] and mb["con_metricas"] and not simuladas:
            linea += (
                f" · Coste: ${mb['coste']:.4f} → ${m['coste']:.4f} · "
                f"Latencia p95: {mb['p95']:.2f} s → {m['p95']:.2f} s"
            )
        print(linea)

    if desactualizadas:
        print(
            "\n❌ Las salidas no corresponden al prompt o a los casos actuales: vuelve a generarlas."
        )
    ok = not criticos and t >= args.umbral and not regresiones and not desactualizadas
    print(f"\nGATE: {'✅ APTO' if ok else '❌ BLOQUEADO'}")
    # resumen que lee la cobertura de requisitos (spec_coverage.py)
    if es_prompt(args.salidas):
        resumen = {
            "prompt": pathlib.Path(args.salidas).as_posix(),
            "huella": actual,
            "modo": "simulado" if simuladas else "api",
            "apto": ok,
            "casos": {
                i: {"k": r["k"], "n": r["n"], "critico": r["critico"]}
                for i, r in resultado.items()
            },
        }
        ruta_resultados(args.salidas, ".evaluacion", ".json").write_text(
            json.dumps(resumen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
