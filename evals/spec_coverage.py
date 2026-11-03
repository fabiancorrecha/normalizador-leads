#!/usr/bin/env python3
"""Trazabilidad spec → test/eval, para cualquier lenguaje. Uso: spec_coverage.py [--raiz DIR] [--junit XML]

En specs APROBADAS falla si un requisito DEBE no tiene evidencia, o si un test cita un requisito
que no existe (código sin spec = el agente se salió del alcance). También falla si una fila de
requisito no tiene prioridad reconocible o si un ID está duplicado: un requisito que la herramienta
no ve daría una cobertura del 100% falsa. Las specs en BORRADOR se muestran como pendientes.

Evidencia:
- Con --junit (informe JUnit XML de pytest, jest-junit, go-junit-report…): solo cuenta un test que
  cita el requisito en su nombre **y pasó**. Un comentario o un test que falla u omitido no cubre.
- Sin --junit: basta con que un test lo cite (por mención). Los evals cuentan en ambos modos.
- Requisitos de IA: un caso de prompts/<f>/casos.jsonl con "requisitos": ["REQ-…"] cubre su requisito si
  pasó todas sus repeticiones en la última evaluación real (make eval-ia), y esa evaluación corresponde
  al prompt y a los casos actuales. Las evaluaciones simuladas o desactualizadas no cuentan.
- Requisitos no funcionales: un test de tests/carga o tests/e2e omitido con la marca [entorno] (no hay
  URL_ENTORNO) no cubre ni falla: se muestra como "se verifica en entorno" (make carga / make e2e,
  y deploy.yml contra staging). La marca fuera de esas carpetas no vale: cuenta como omitido.

Requisitos y tareas: si la spec tiene tasks.md, un requisito DEBE se exige cuando alguna tarea que lo cita
está terminada (✅) o es la tarea activa (.kit/tarea-actual, KIT_TAREA o el nombre de la rama). Los que
solo citan tareas pendientes salen como "pendiente (T-…)": así cada tarea termina en verde sin esperar a
las siguientes, y al acabar la fase se exigen todos. Un requisito que ninguna tarea cita se exige siempre:
es un hueco del plan.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "evals" / "ia"))
from comun import (
    huella,
)

FILA_REQ = re.compile(r"^\|\s*(REQ-[A-Z0-9]+-\d{3,})\s*\|(.*)$", re.MULTILINE)
REF = re.compile(r"REQ[-_]([A-Z0-9]+)[-_](\d{3,})")
APROBADA = re.compile(r"Estado:\s*\**\s*APROBADA")
PRIORIDADES = {
    "DEBE": "DEBE",
    "DEBERÍA": "DEBERÍA",
    "DEBERIA": "DEBERÍA",
    "MUST": "DEBE",
    "SHOULD": "DEBERÍA",
}
EXT = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".go",
    ".java",
    ".kt",
    ".rb",
    ".cs",
    ".rs",
    ".php",
}
IGNORAR = {
    "node_modules",
    ".git",
    ".venv",
    "venv",
    "dist",
    "build",
    ".claude",
    "__pycache__",
    "specs",
    ".pytest_cache",
    ".kit-backup",
}
NO_EVIDENCIA = {
    "spec_coverage.py",
    "test_guardrails.py",
    "test_reglas_proyecto.py",
    "test_kit.py",
}
CARPETA_ENTORNO = re.compile(r"(^|[./\\])(carga|e2e)[./\\]")
ID_TAREA = re.compile(r"T-B?\d+(?:-\d+)?", re.IGNORECASE)
TAREA_EN_RAMA = re.compile(r"\bT-(B?\d+)-(\d+)\b", re.IGNORECASE)
# REQ-AUD-001..003 en una tarea cita los tres
RANGO_REQ = re.compile(r"(REQ-[A-Z0-9]+-)(\d{3,})(?:\.\.(\d{3,}))?")


def tareas_por_requisito(carpeta: pathlib.Path) -> dict[str, list[tuple[str, bool]]]:
    """REQ → [(tarea, terminada)] según el tasks.md de la spec. Vacío si no hay tasks.md."""
    tasks = carpeta / "tasks.md"
    if not tasks.is_file():
        return {}
    por_requisito: dict[str, list[tuple[str, bool]]] = {}
    cabecera = None
    for linea in tasks.read_text(encoding="utf-8").splitlines():
        celdas = [c.strip() for c in linea.strip().strip("|").split("|")]
        if cabecera is None and any("requisito" in c.lower() for c in celdas):
            cabecera = [c.lower() for c in celdas]
        elif cabecera and celdas and ID_TAREA.fullmatch(celdas[0]):
            fila = dict(zip(cabecera, celdas))
            citados = next((v for k, v in fila.items() if "requisito" in k), "")
            terminada = "✅" in fila.get("estado", "")
            for prefijo, desde, hasta in RANGO_REQ.findall(citados):
                fin = min(int(hasta or desde), int(desde) + 50)
                for n in range(int(desde), fin + 1):
                    por_requisito.setdefault(f"{prefijo}{n:0{len(desde)}d}", []).append(
                        (celdas[0].upper(), terminada)
                    )
    return por_requisito


def tarea_activa(raiz: pathlib.Path) -> str | None:
    """La tarea en curso: KIT_TAREA, la que activó /implementar o la del nombre de la rama (también en CI)."""
    if os.environ.get("KIT_TAREA"):
        return os.environ["KIT_TAREA"].upper()
    try:
        datos = json.loads((raiz / ".kit" / "tarea-actual").read_text(encoding="utf-8"))
        if isinstance(datos, dict) and datos.get("id"):
            return str(datos["id"]).upper()
    except (OSError, ValueError):
        pass
    try:
        rama = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=raiz,
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
    except OSError:
        rama = ""
    m = TAREA_EN_RAMA.search(rama or os.environ.get("GITHUB_HEAD_REF", ""))
    return f"T-{m.group(1)}-{m.group(2)}".upper() if m else None


def es_evidencia(p: pathlib.Path, raiz: pathlib.Path) -> bool:
    parts = set(p.relative_to(raiz).parts)
    name = p.name.lower()
    return (
        p.suffix in EXT
        and not parts & IGNORAR
        and p.name not in NO_EVIDENCIA
        and (
            "test" in name
            or ".spec." in name
            or bool(parts & {"tests", "__tests__", "evals"})
        )
    )


def resultados_junit(xml: pathlib.Path) -> dict[str, list[str]]:
    """REQ → estados ('ok', 'falla', 'entorno', 'omitido') de los tests que lo citan en su nombre o clase."""
    estados: dict[str, list[str]] = {}
    for caso in ET.parse(xml).getroot().iter("testcase"):
        hijos = {h.tag for h in caso}
        omitido = caso.find("skipped")
        if hijos & {"failure", "error"}:
            estado = "falla"
        elif omitido is not None:
            motivo = f"{omitido.get('message', '')} {omitido.text or ''}"
            donde = f"{caso.get('classname', '')} {caso.get('file', '')}"
            estado = (
                "entorno"
                if "[entorno]" in motivo and CARPETA_ENTORNO.search(donde)
                else "omitido"
            )
        else:
            estado = "ok"
        for m in REF.finditer(f"{caso.get('classname', '')} {caso.get('name', '')}"):
            estados.setdefault(f"REQ-{m.group(1)}-{m.group(2)}", []).append(estado)
    return estados


def resultados_evals(raiz: pathlib.Path) -> dict[str, list[tuple[str, str]]]:
    """REQ → [(estado, versión)] de los casos de eval de IA que lo citan en "requisitos"."""
    estados: dict[str, list[tuple[str, str]]] = {}
    for casos in sorted(raiz.glob("prompts/*/casos.jsonl")):
        carpeta = casos.parent
        if carpeta.name.startswith("_"):
            continue
        resumenes = sorted(
            carpeta.glob("resultados/v*.evaluacion.json"),
            key=lambda p: int(re.match(r"v(\d+)", p.name).group(1)),
        )
        resumen = (
            json.loads(resumenes[-1].read_text(encoding="utf-8")) if resumenes else None
        )
        version = resumenes[-1].name.split(".")[0] if resumenes else "sin evaluar"
        prompt = carpeta / f"{version}.md"
        texto = casos.read_text(encoding="utf-8")
        fresca = (
            bool(resumen)
            and prompt.exists()
            and resumen.get("huella")
            == huella(prompt.read_text(encoding="utf-8"), texto)
        )
        for linea in filter(str.strip, texto.splitlines()):
            caso = json.loads(linea)
            requisitos = caso.get("requisitos") or []
            for rid in [requisitos] if isinstance(requisitos, str) else requisitos:
                r = (resumen or {}).get("casos", {}).get(caso.get("id"))
                if resumen is None:
                    estado = "sin evaluar"
                elif resumen.get("modo") == "simulado":
                    estado = "simulado"
                elif not fresca:
                    estado = "desactualizado"
                else:
                    estado = "ok" if r and r["k"] == r["n"] else "falla"
                estados.setdefault(rid.upper(), []).append(
                    (estado, f"{carpeta.name}/{version}")
                )
    return estados


def prioridad(resto_de_fila: str) -> str | None:
    for celda in resto_de_fila.split("|"):
        valor = celda.strip().strip("*_ ").upper()
        if valor in PRIORIDADES:
            return PRIORIDADES[valor]
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raiz", type=pathlib.Path, default=ROOT)
    ap.add_argument("--junit", type=pathlib.Path)
    args = ap.parse_args()
    raiz = args.raiz.resolve()

    reqs: dict[str, tuple[str, bool, str]] = {}
    errores: list[str] = []
    activa = tarea_activa(raiz)
    espera: dict[
        str, list[str]
    ] = {}  # requisito → tareas pendientes de las que depende
    sin_tarea: set[str] = set()  # requisitos que ninguna tarea cita (con tasks.md)
    for spec in sorted(raiz.glob("specs/*/spec.md")):
        if spec.parent.name.startswith("_"):
            continue
        text = spec.read_text(encoding="utf-8")
        aprobada = bool(APROBADA.search(text[:600]))
        por_requisito = tareas_por_requisito(spec.parent)
        for rid, resto in FILA_REQ.findall(text):
            citas = por_requisito.get(rid, [])
            if por_requisito and not citas:
                sin_tarea.add(rid)
            elif citas and not any(hecha or t == activa for t, hecha in citas):
                espera[rid] = sorted({t for t, _ in citas})
            prio = prioridad(resto)
            if rid in reqs:
                errores.append(
                    f"{rid} duplicado en {reqs[rid][2]} y {spec.parent.name}"
                )
            if prio is None:
                errores.append(
                    f"{rid} ({spec.parent.name}) sin prioridad reconocible (DEBE/DEBERÍA/MUST/SHOULD)"
                )
                prio = "DEBE"  # en caso de duda, se exige
            reqs.setdefault(rid, (prio, aprobada, spec.parent.name))

    if not reqs:
        print("Aún no hay requisitos en specs/*/spec.md.")
        return 0

    junit: dict[str, list[str]] | None = None
    if args.junit:
        if not args.junit.is_file():
            print(
                f"❌ No encuentro el informe JUnit en {args.junit}: ejecuta antes los tests (make check lo hace)."
            )
            return 1
        try:
            junit = resultados_junit(args.junit)
        except ET.ParseError as error:
            print(f"❌ El informe JUnit {args.junit} no es XML válido: {error}")
            return 1

    evals_ia = resultados_evals(raiz)
    menciones: dict[str, set[str]] = {}
    for f in raiz.rglob("*"):
        # Con JUnit, los tests cuentan por su resultado; las menciones solo valen en los evals.
        if (
            f.is_file()
            and es_evidencia(f, raiz)
            and (junit is None or "evals" in f.relative_to(raiz).parts)
        ):
            for m in REF.finditer(f.read_text(encoding="utf-8", errors="ignore")):
                menciones.setdefault(f"REQ-{m.group(1)}-{m.group(2)}", set()).add(
                    f.name
                )

    def evidencia(rid: str) -> tuple[str, str]:
        """('cubierto' | 'entorno' | 'no', descripción)."""
        partes, estado = [], "cubierto" if menciones.get(rid) else "no"
        if junit is not None:
            estados = junit.get(rid, [])
            if "ok" in estados:
                partes.append(f"test ✓ ({estados.count('ok')})")
                estado = "cubierto"
            elif "falla" in estados:
                partes.append("❌ test falla")
            elif "entorno" in estados and estado == "no":
                partes.append("⏳ se verifica en entorno")
                estado = "entorno"
            elif "omitido" in estados:
                partes.append("⚠ test omitido")
        casos_ia = evals_ia.get(rid, [])
        if casos_ia:  # con casos de eval, mandan ellos: un test de la fontanería no prueba al modelo
            de = casos_ia[0][1]
            malos = [e for e, _ in casos_ia if e != "ok"]
            if not malos:
                partes.append(f"eval ✓ ({len(casos_ia)} caso(s), {de})")
                estado = "cubierto"
            else:
                partes.append(
                    {
                        "falla": f"❌ eval falla ({de})",
                        "desactualizado": f"⚠ eval desactualizado ({de}): vuelve a ejecutar make eval-ia",
                        "simulado": f"⚠ eval simulado ({de}): no cuenta como evidencia",
                        "sin evaluar": "⚠ eval sin ejecutar",
                    }[malos[0]]
                )
                estado = "no"
        partes += sorted(menciones.get(rid, []))
        return estado, ", ".join(partes)

    print(f"{'Requisito':<14} {'Prio':<8} {'Spec':<9} Evidencia")
    cubiertos = {}
    for rid, (prio, aprobada, _) in reqs.items():
        exigible = aprobada and prio == "DEBE" and rid not in espera
        cubiertos[rid], texto = evidencia(rid)
        if cubiertos[rid] == "no":
            if exigible:
                motivo = "❌ SIN TEST QUE PASE"
                if rid in sin_tarea:
                    motivo += " (ninguna tarea lo cita)"
            elif rid in espera:
                motivo = f"pendiente ({', '.join(espera[rid])})"
            else:
                motivo = "pendiente"
            texto = (texto + " · " if texto else "") + motivo
        print(
            f"{rid:<14} {prio:<8} {'aprobada' if aprobada else 'borrador':<9} {texto}"
        )

    exigibles = [
        r for r, (p, a, _) in reqs.items() if p == "DEBE" and a and r not in espera
    ]
    en_espera = [
        r for r, (p, a, _) in reqs.items() if p == "DEBE" and a and r in espera
    ]
    missing = [r for r in exigibles if cubiertos[r] == "no"]
    en_entorno = [r for r in exigibles if cubiertos[r] == "entorno"]
    orphans = sorted((set(menciones) | set(junit or {}) | set(evals_ia)) - set(reqs))
    modo = (
        f"tests que pasan (JUnit: {args.junit})"
        if junit is not None
        else "menciones en tests (con JUnit solo contarían los que pasan)"
    )
    print(f"\nEvidencia: {modo}")
    if exigibles:
        print(
            f"Cobertura DEBE (specs aprobadas): {len(exigibles) - len(missing) - len(en_entorno)}/{len(exigibles)}"
            + (f" · {len(en_entorno)} se verifican en entorno" if en_entorno else "")
        )
    if en_espera:
        tareas = sorted({t for r in en_espera for t in espera[r]})
        print(
            f"⏳ {len(en_espera)} requisito(s) DEBE esperan a sus tareas pendientes ({', '.join(tareas)}): "
            "se exigen cuando la tarea está activa o terminada (✅)."
        )
    if en_entorno:
        print(
            f"⏳ Sin entorno aquí; los verifican make carga / make e2e con URL_ENTORNO (deploy.yml, contra "
            f"staging): {', '.join(en_entorno)}"
        )
    for error in errores:
        print(f"❌ {error}")
    if orphans:
        print(f"❌ Tests que citan requisitos inexistentes: {', '.join(orphans)}")
    if missing:
        print(f"❌ Requisitos DEBE sin test: {', '.join(missing)}")
    return 1 if missing or orphans or errores else 0


if __name__ == "__main__":
    sys.exit(main())
