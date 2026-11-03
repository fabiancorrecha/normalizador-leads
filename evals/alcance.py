#!/usr/bin/env python3
"""Alcance de la tarea: ¿los cambios tocan solo los "Archivos permitidos" de la tarea activa?

Uso:
  alcance.py --iniciar T-002-1   activa la tarea (lo hace /implementar): guarda el commit de partida
                                 y una instantánea de sus archivos permitidos en .kit/tarea-actual
  alcance.py                     comprueba (lo ejecuta `make check`: el hook Stop y la CI)
  alcance.py --terminar          desactiva la tarea
  alcance.py --nota "…" [--siguiente "…"]
                                 apunta un paso de la tarea activa en specs/<spec>/progreso.md, la bitácora
                                 que lee el hook de inicio de sesión para no perder el contexto
  alcance.py --solapes [T-…]     qué tareas pendientes (o las indicadas) pueden ir en paralelo, cada una en
                                 su worktree, sin tocar los mismos archivos
La tarea activa sale de --tarea, de KIT_TAREA, de .kit/tarea-actual o del nombre de la rama
(p. ej. `t-002-1-cobro-idempotente`). Sin tarea activa no comprueba nada.
Siempre se permiten la carpeta de la spec de la tarea, `.kit/` y `docs/recomendaciones.md` (/implementar
apunta ahí lo que ve fuera del alcance), y se ignoran los worktrees de otras
sesiones (`.claude/worktrees/`). Admite comodines (`src/pagos/**`).
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
ID_TAREA = re.compile(r"\bT-(B?\d+)-(\d+)\b", re.IGNORECASE)


def git(raiz: pathlib.Path, *args: str) -> str | None:
    r = subprocess.run(
        ["git", *args], cwd=raiz, capture_output=True, text=True, check=False
    )
    return r.stdout.strip() if r.returncode == 0 else None


def buscar(raiz: pathlib.Path, tarea: str) -> tuple[str, list[str]] | None:
    """(carpeta de la spec, archivos permitidos) de la tarea en specs/*/tasks.md."""
    for tasks in sorted(raiz.glob("specs/*/tasks.md")):
        if tasks.parent.name.startswith("_"):
            continue
        columna = None
        for linea in tasks.read_text(encoding="utf-8").splitlines():
            celdas = [c.strip() for c in linea.strip().strip("|").split("|")]
            if columna is None and any("archivos" in c.lower() for c in celdas):
                columna = next(
                    i for i, c in enumerate(celdas) if "archivos" in c.lower()
                )
            elif (
                celdas
                and celdas[0].upper() == tarea
                and columna is not None
                and columna < len(celdas)
            ):
                return f"specs/{tasks.parent.name}", re.findall(
                    r"`([^`]+)`", celdas[columna]
                )
    return None


def tareas(raiz: pathlib.Path) -> dict[str, tuple[list[str], bool]]:
    """ID → (archivos permitidos, terminada) de todas las tareas de specs/*/tasks.md."""
    todas = {}
    for tasks in sorted(raiz.glob("specs/*/tasks.md")):
        if tasks.parent.name.startswith("_"):
            continue
        cabecera = None
        for linea in tasks.read_text(encoding="utf-8").splitlines():
            celdas = [c.strip() for c in linea.strip().strip("|").split("|")]
            if cabecera is None and any("archivos" in c.lower() for c in celdas):
                cabecera = [c.lower() for c in celdas]
            # también T-004
            elif (
                cabecera
                and celdas
                and re.fullmatch(r"T-B?\d+(?:-\d+)?", celdas[0], re.IGNORECASE)
            ):
                fila = dict(zip(cabecera, celdas))
                archivos = next((v for k, v in fila.items() if "archivos" in k), "")
                todas[celdas[0].upper()] = (
                    re.findall(r"`([^`]+)`", archivos),
                    "✅" in fila.get("estado", ""),
                )
    return todas


def prefijo(patron: str) -> str:
    """Parte fija de un patrón hasta su primer comodín (cortada en la última /): lo que seguro abarca."""
    patron = patron.strip().removeprefix("./")
    corte = min((patron.find(c) for c in "*?[" if c in patron), default=-1)
    return patron if corte < 0 else patron[: patron.rfind("/", 0, corte) + 1]


def se_solapan(a: list[str], b: list[str]) -> list[tuple[str, str]]:
    """Pares de patrones que podrían abarcar el mismo archivo. Conservador: ante la duda, se solapan."""
    return [
        (x, y)
        for x in a
        for y in b
        if prefijo(x).startswith(prefijo(y)) or prefijo(y).startswith(prefijo(x))
    ]


def solapes(raiz: pathlib.Path, pedidas: list[str]) -> int:
    todas = tareas(raiz)
    ids = [t.upper() for t in pedidas] or [
        t for t, (_, hecha) in todas.items() if not hecha
    ]
    faltan = [t for t in ids if t not in todas]
    if faltan:
        print(f"❌ No encuentro en specs/*/tasks.md: {', '.join(faltan)}")
        return 1
    if not ids:
        print("No hay tareas pendientes.")
        return 0
    sin_archivos = [t for t in ids if not todas[t][0]]
    for t in sin_archivos:
        print(
            f"⚠ {t} no declara archivos permitidos: no se puede paralelizar con seguridad."
        )
    conflictos = {t: set() for t in ids}
    for i, a in enumerate(ids):
        for b in ids[i + 1 :]:
            pares = se_solapan(todas[a][0], todas[b][0])
            if pares or a in sin_archivos or b in sin_archivos:
                conflictos[a].add(b)
                conflictos[b].add(a)
                if pares:
                    print(
                        f"⚠ {a} y {b} pueden tocar lo mismo: {pares[0][0]} ↔ {pares[0][1]}"
                    )
    tandas: list[list[str]] = []
    # reparto voraz: cada tarea va a la primera tanda donde no choca con nadie
    for t in ids:
        destino = next(
            (tanda for tanda in tandas if not conflictos[t] & set(tanda)), None
        )
        if destino is None:
            tandas.append(destino := [])
        destino.append(t)
    for n, tanda in enumerate(tandas, 1):
        modo = "en paralelo, un worktree por tarea" if len(tanda) > 1 else "sola"
        print(f"Tanda {n} ({modo}): {', '.join(tanda)}")
    return 0


def a_regex(patron: str, raiz: pathlib.Path) -> re.Pattern:
    patron = patron.strip().removeprefix("./")
    if patron.endswith("/") or (raiz / patron).is_dir():
        patron = patron.rstrip("/") + "/**"
    regex, i = "", 0
    while i < len(patron):
        if patron.startswith("**/", i):
            regex, i = regex + "(?:.*/)?", i + 3
        elif patron.startswith("**", i):
            regex, i = regex + ".*", i + 2
        elif patron[i] == "*":
            regex, i = regex + "[^/]*", i + 1
        elif patron[i] == "?":
            regex, i = regex + "[^/]", i + 1
        else:
            regex, i = regex + re.escape(patron[i]), i + 1
    return re.compile(regex + "$")


CABECERA_PROGRESO = """# Progreso de {spec}

Bitácora de las tareas: una línea por paso, la más reciente al final. La escribe /implementar con
`python3 evals/alcance.py --nota "…" --siguiente "…"` y la lee el hook de inicio de sesión, para que el
contexto de la tarea sobreviva a /clear, a la compactación de la conversación y a una sesión nueva.

"""


def una_linea(texto: str, largo: int = 300) -> str:
    texto = " ".join(texto.replace("|", "/").split())
    return texto if len(texto) <= largo else texto[: largo - 1] + "…"


def apuntar(
    raiz: pathlib.Path, spec: str, tarea: str, nota: str, siguiente: str | None
) -> str:
    """Añade una línea a specs/<spec>/progreso.md (lo crea si falta) y la devuelve."""
    archivo = raiz / spec / "progreso.md"
    ahora = datetime.datetime.now(datetime.timezone.utc).astimezone()
    linea = f"{ahora:%Y-%m-%d %H:%M} · {tarea} · {una_linea(nota)}"
    if siguiente:
        linea += f" · siguiente: {una_linea(siguiente)}"
    if not archivo.exists():
        archivo.write_text(
            CABECERA_PROGRESO.format(spec=spec.removeprefix("specs/")),
            encoding="utf-8",
        )
    with open(archivo, "a", encoding="utf-8") as f:
        f.write(f"- {linea}\n")
    return linea


def base_por_defecto(raiz: pathlib.Path) -> str:
    for rama in ("origin/main", "origin/master", "main", "master"):
        base = git(raiz, "merge-base", "HEAD", rama)
        if base:
            return base
    return "HEAD"


def tarea_activa(raiz: pathlib.Path, explicita: str | None) -> dict | None:
    archivo = raiz / ".kit" / "tarea-actual"
    if explicita or os.environ.get("KIT_TAREA"):
        return {"id": (explicita or os.environ["KIT_TAREA"]).upper()}
    if archivo.is_file():
        return json.loads(archivo.read_text(encoding="utf-8"))
    m = ID_TAREA.search(git(raiz, "branch", "--show-current") or "")
    return {"id": f"T-{m.group(1)}-{m.group(2)}".upper()} if m else None


def main() -> int:
    ap = argparse.ArgumentParser()
    # no CLAUDE_PROJECT_DIR: en un worktree es otro checkout
    ap.add_argument("--raiz", type=pathlib.Path, default=ROOT)
    ap.add_argument("--tarea")
    ap.add_argument("--iniciar", metavar="TAREA")
    ap.add_argument("--terminar", action="store_true")
    ap.add_argument("--solapes", nargs="*", metavar="TAREA")
    ap.add_argument("--nota", metavar="TEXTO")
    ap.add_argument("--siguiente", metavar="TEXTO")
    args = ap.parse_args()
    raiz = args.raiz.resolve()
    kit = raiz / ".kit"

    if args.solapes is not None:
        return solapes(raiz, args.solapes)

    if args.nota:
        activa = tarea_activa(raiz, args.tarea)
        encontrada = buscar(raiz, activa["id"]) if activa else None
        spec = (activa or {}).get("spec") or (encontrada[0] if encontrada else None)
        if not activa or not spec:
            print(
                "❌ No hay una tarea activa que esté en specs/*/tasks.md: "
                "actívala con --iniciar T-… (lo hace /implementar)."
            )
            return 1
        linea = apuntar(raiz, spec, activa["id"], args.nota, args.siguiente)
        print(f"Anotado en {spec}/progreso.md: {linea}")
        return 0

    if args.terminar:
        (kit / "tarea-actual").unlink(missing_ok=True)
        print("Tarea desactivada: el alcance ya no se comprueba.")
        return 0
    if args.iniciar:
        tarea = args.iniciar.upper()
        encontrada = buscar(raiz, tarea)
        if not encontrada:
            print(f"❌ No encuentro {tarea} en specs/*/tasks.md.")
            return 1
        spec, permitidos = encontrada
        kit.mkdir(exist_ok=True)
        estado = {
            "id": tarea,
            "spec": spec,
            "permitidos": permitidos,
            "base": git(raiz, "rev-parse", "HEAD") or "HEAD",
        }
        (kit / "tarea-actual").write_text(
            json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        previas = raiz / spec / "progreso.md"
        retomada = previas.exists() and re.search(
            rf"· {re.escape(tarea)} ·", previas.read_text(encoding="utf-8")
        )
        apuntar(raiz, spec, tarea, "retomada" if retomada else "iniciada", None)
        print(
            f"Tarea activa: {tarea} ({spec}) · permitidos: {', '.join(permitidos) or '(ninguno)'}"
        )
        return 0

    if git(raiz, "rev-parse", "--is-inside-work-tree") != "true":
        print("Alcance: no es un repositorio git, no se comprueba.")
        return 0
    activa = tarea_activa(raiz, args.tarea)
    if not activa:
        print("Alcance: sin tarea activa, no se comprueba.")
        return 0
    encontrada = buscar(raiz, activa["id"])
    if not encontrada and "permitidos" not in activa:
        print(f"❌ La tarea activa {activa['id']} no está en specs/*/tasks.md.")
        return 1
    spec, permitidos_ahora = encontrada or (activa["spec"], activa["permitidos"])
    permitidos = activa.get("permitidos", permitidos_ahora)
    if (
        encontrada
        and "permitidos" in activa
        and sorted(permitidos_ahora) != sorted(permitidos)
    ):
        print(
            f"⚠ La lista de archivos permitidos de {activa['id']} ha cambiado desde que empezó la tarea; "
            "se comprueba con la de entonces. Si el cambio es legítimo, vuelve a iniciar la tarea."
        )

    base = os.environ.get("KIT_BASE") or activa.get("base") or base_por_defecto(raiz)
    cambiados = set((git(raiz, "diff", "--name-only", base) or "").splitlines())
    cambiados |= set(
        (git(raiz, "ls-files", "--others", "--exclude-standard") or "").splitlines()
    )
    cambiados = {
        c for c in cambiados if not c.startswith(".claude/worktrees/")
    }  # otras sesiones en paralelo
    reglas = [a_regex(p, raiz) for p in permitidos] + [
        a_regex(spec + "/", raiz),
        a_regex(".kit/", raiz),
        a_regex("docs/recomendaciones.md", raiz),
    ]
    fuera = sorted(f for f in cambiados if f and not any(r.match(f) for r in reglas))

    print(
        f"Alcance de {activa['id']} ({spec}): permitidos {', '.join(permitidos) or '(ninguno)'}"
    )
    if fuera:
        print(f"❌ Fuera del alcance: {', '.join(fuera)}")
        print(
            "   Si de verdad hace falta, añádelo a «Archivos permitidos» de la tarea (y que lo vea quien revisa)"
            " o sepáralo en otra tarea."
        )
        return 1
    print(f"Alcance: {len(cambiados)} archivo(s) cambiado(s), todos dentro ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
