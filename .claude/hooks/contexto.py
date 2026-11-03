#!/usr/bin/env python3
"""SessionStart: devuelve a Claude el contexto de la tarea al empezar, tras /clear y tras compactar.

Lo que importa no vive en la conversación sino en archivos: la tarea activa (.kit/tarea-actual, que pone
/implementar), su fila en specs/*/tasks.md, sus requisitos, la bitácora specs/<spec>/progreso.md, los
cambios sin commit y, si existe, el estado del mapa del código (graphify-out/). Lo que este hook imprime
entra en el contexto de Claude: así retoma la tarea donde la dejó aunque la conversación se haya perdido.

No bloquea nunca: si algo no se puede leer, lo omite y sale con 0. Solo lee archivos y git.
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

MAXIMO = 6000  # caracteres; Claude Code recorta lo que pasa de 10.000
NOTAS = 3
ORIGEN = {
    "startup": "al empezar la sesión",
    "resume": "al retomar la sesión",
    "clear": "tras /clear",
    "compact": "tras compactar la conversación",
}


def leer(ruta: pathlib.Path) -> str:
    try:
        return ruta.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def git(raiz: pathlib.Path, *args: str) -> str | None:
    try:
        r = subprocess.run(
            ["git", *args],
            cwd=raiz,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def celdas(linea: str) -> list[str]:
    return [c.strip() for c in linea.strip().strip("|").split("|")]


def tareas(raiz: pathlib.Path) -> list[dict]:
    """Las filas de specs/*/tasks.md: id, título, requisitos, archivos, si está hecha y su spec."""
    filas = []
    for tasks in sorted(raiz.glob("specs/*/tasks.md")):
        if tasks.parent.name.startswith("_"):
            continue
        cabecera = None
        for linea in leer(tasks).splitlines():
            c = celdas(linea)
            if cabecera is None and any("archivos" in x.lower() for x in c):
                cabecera = [x.lower() for x in c]
            elif (
                cabecera
                and c
                and re.fullmatch(r"T-B?\d+(?:-\d+)?", c[0], re.IGNORECASE)
            ):
                fila = dict(zip(cabecera, c))
                columna = next((v for k, v in fila.items() if "archivos" in k), "")
                filas.append(
                    {
                        "id": c[0].upper(),
                        "titulo": fila.get("tarea", ""),
                        "requisitos": next(
                            (v for k, v in fila.items() if "requisito" in k), ""
                        ),
                        "archivos": re.findall(r"`([^`]+)`", columna),
                        "hecha": "✅" in fila.get("estado", ""),
                        "spec": tasks.parent.name,
                    }
                )
    return filas


def ids_de(requisitos: str) -> list[str]:
    """`REQ-AUD-001..003` → REQ-AUD-001, REQ-AUD-002 y REQ-AUD-003."""
    ids = []
    for prefijo, desde, hasta in re.findall(
        r"(REQ-[A-Z0-9]+-)(\d{3,})(?:\.\.(\d{3,}))?", requisitos
    ):
        fin = min(int(hasta or desde), int(desde) + 20)
        ids += [f"{prefijo}{n:0{len(desde)}d}" for n in range(int(desde), fin + 1)]
    return ids


def requisitos_de(raiz: pathlib.Path, spec: str) -> dict[str, str]:
    textos = {}
    for linea in leer(raiz / "specs" / spec / "spec.md").splitlines():
        c = celdas(linea)
        if len(c) >= 2 and re.fullmatch(r"REQ-[A-Z0-9]+-\d{3,}", c[0]):
            textos[c[0]] = c[1]
    return textos


def aprobada(raiz: pathlib.Path, spec: str) -> bool:
    cabeza = leer(raiz / "specs" / spec / "spec.md")[:600]
    return bool(re.search(r"Estado:\s*\**\s*APROBADA", cabeza))


def notas(raiz: pathlib.Path, spec: str, tarea: str) -> list[str]:
    lineas = [
        linea.strip()[2:]
        for linea in leer(raiz / "specs" / spec / "progreso.md").splitlines()
        if linea.strip().startswith("- ")
    ]
    return [
        n for n in lineas if re.search(rf"\b{re.escape(tarea)}\b", n, re.IGNORECASE)
    ][-NOTAS:]


def tarea_activa(raiz: pathlib.Path) -> dict | None:
    try:
        datos = json.loads(leer(raiz / ".kit" / "tarea-actual") or "null")
    except json.JSONDecodeError:
        datos = None
    if isinstance(datos, dict) and datos.get("id"):
        return datos
    m = re.search(
        r"\bT-(B?\d+)-(\d+)\b",
        git(raiz, "branch", "--show-current") or "",
        re.IGNORECASE,
    )
    return {"id": f"T-{m.group(1)}-{m.group(2)}".upper()} if m else None


def cambios(raiz: pathlib.Path) -> list[str]:
    try:
        r = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=raiz,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    # sin strip(): cada línea empieza por dos columnas de estado y un espacio (" M .claude/x")
    return (
        [linea[3:] for linea in r.stdout.splitlines() if linea[3:]]
        if r.returncode == 0
        else []
    )


def estado_mapa(raiz: pathlib.Path, cambiados: list[str]) -> str | None:
    """Si hay mapa de graphify: al día o desactualizado (otro commit o código cambiado después)."""
    grafo = raiz / "graphify-out" / "graph.json"
    try:
        tamano, momento = grafo.stat().st_size, grafo.stat().st_mtime
        with open(
            grafo, "rb"
        ) as f:  # el commit va al final: no hace falta leer un grafo enorme
            f.seek(max(0, tamano - 4096))
            cola = f.read().decode("utf-8", "replace")
    except OSError:
        return None
    m = re.search(r'"built_at_commit"\s*:\s*"([0-9a-f]{7,40})"', cola)
    head = git(raiz, "rev-parse", "HEAD")
    if m and head and m.group(1) != head:
        return f"desactualizado (es del commit {m.group(1)[:7]}; HEAD es {head[:7]})"
    for ruta in cambiados:
        try:
            if (raiz / ruta).stat().st_mtime > momento:
                return f"desactualizado ({ruta} cambió después)"
        except OSError:
            continue
    return "al día"


def recortar(texto: str, largo: int = 220) -> str:
    texto = " ".join(texto.split())
    return texto if len(texto) <= largo else texto[: largo - 1] + "…"


def resumen(raiz: pathlib.Path, origen: str) -> str:
    momento = ORIGEN.get(origen, "al empezar")
    cabecera = (
        f"Contexto del proyecto que da el kit {momento}. "
        "Los archivos mandan sobre lo que recuerdes de la conversación:"
    )
    lineas = [cabecera]
    titulo = next(
        (
            linea[2:].strip()
            for linea in leer(raiz / "CLAUDE.md").splitlines()
            if linea.startswith("# ")
        ),
        "",
    )
    if titulo and "[NOMBRE DEL PROYECTO]" not in titulo:
        lineas.append(f"- Proyecto: {titulo}")

    todas = tareas(raiz)
    activa = tarea_activa(raiz)
    cambiados = cambios(raiz)
    if activa:
        fila = next((t for t in todas if t["id"] == activa["id"].upper()), None)
        spec = (activa.get("spec") or (fila or {}).get("spec") or "").removeprefix(
            "specs/"
        )
        estado = ("APROBADA" if aprobada(raiz, spec) else "en BORRADOR") if spec else ""
        lineas.append(
            f"- Tarea activa: {activa['id']}"
            + (f" «{recortar(fila['titulo'], 120)}»" if fila else "")
            + (f" · specs/{spec} ({estado})" if spec else "")
        )
        if fila:
            textos = requisitos_de(raiz, fila["spec"])
            for rid in ids_de(fila["requisitos"])[:8]:
                lineas.append(
                    f"  · {rid}: {recortar(textos.get(rid, '(no está en la spec)'))}"
                )
        permitidos = activa.get("permitidos") or (fila or {}).get("archivos") or []
        if permitidos:
            lineas.append("  Archivos permitidos: " + ", ".join(permitidos[:15]))
        if cambiados:
            extra = f" y {len(cambiados) - 15} más" if len(cambiados) > 15 else ""
            lineas.append("  Cambios sin commit: " + ", ".join(cambiados[:15]) + extra)
        ultimas = notas(raiz, spec, activa["id"]) if spec else []
        if ultimas:
            lineas.append(f"  Últimas notas (specs/{spec}/progreso.md):")
            lineas += [f"  · {recortar(n, 300)}" for n in ultimas]
            siguiente = re.search(r"siguiente:\s*(.+)$", ultimas[-1], re.IGNORECASE)
            if siguiente:
                lineas.append(f"  Siguiente paso: {recortar(siguiente.group(1))}")
        else:
            lineas.append(
                "  Sin notas de progreso: apunta cada paso con "
                '`python3 evals/alcance.py --nota "…" --siguiente "…"`.'
            )
    else:
        pendientes = [t for t in todas if not t["hecha"] and aprobada(raiz, t["spec"])]
        if pendientes:
            lista = ", ".join(
                f"{t['id']} «{recortar(t['titulo'], 60)}»" for t in pendientes[:3]
            )
            lineas.append(
                f"- Sin tarea activa. Pendientes en specs aprobadas: {lista}. "
                f"Para empezar: /implementar {pendientes[0]['id']}."
            )
        elif todas:
            lineas.append(
                "- Sin tarea activa ni tareas pendientes en specs aprobadas: "
                "¿hay una spec en BORRADOR que aprobar?"
            )
        else:
            lineas.append(
                "- Aún no hay specs: empieza con /kit (o /descubrir si es una idea)."
            )

    mapa = estado_mapa(raiz, cambiados)
    if mapa == "al día":
        lineas.append(
            "- Mapa del código (graphify-out/, al día): para entender código, antes de leer archivos enteros, "
            '`graphify explain "<símbolo>"`, `graphify affected "<símbolo>"` (qué depende de él), '
            '`graphify path "<A>" "<B>"` o `graphify query "<pregunta>"`.'
        )
    elif mapa:
        lineas.append(
            f"- Mapa del código {mapa}: ejecuta `make mapa` antes de fiarte de él."
        )
    lineas.append(
        "- Sigue CLAUDE.md, no salgas de los archivos permitidos y no des nada por terminado sin "
        "`make check` en verde."
    )
    texto = "\n".join(lineas)
    return texto if len(texto) <= MAXIMO else texto[: MAXIMO - 20] + "\n… (recortado)"


def main() -> int:
    try:
        entrada = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        entrada = {}
    entrada = entrada if isinstance(entrada, dict) else {}
    try:
        from raiz import raiz_de_trabajo

        texto = resumen(
            pathlib.Path(raiz_de_trabajo(entrada)), entrada.get("source", "")
        )
    except Exception as error:  # noqa: BLE001 — un fallo aquí no puede impedir que empiece la sesión
        texto = (
            f"(El kit no pudo resumir el contexto de la tarea: {type(error).__name__}. "
            "Lee .kit/tarea-actual y specs/*/progreso.md.)"
        )
    print(texto)
    return 0


if __name__ == "__main__":
    sys.exit(main())
