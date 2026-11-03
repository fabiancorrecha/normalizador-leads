#!/usr/bin/env python3
"""CI: evalúa cada versión de prompt añadida o cambiada contra su versión anterior.

Uso: cambiados.py [--desde origin/main] [--repeticiones 3] [--simulado]

Para cada prompts/<f>/vN.md cambiado desde la referencia (o cuyos resultados cambian en el PR): genera
sus salidas siempre de nuevo (no se fía de resultados que vengan en el propio PR), reutiliza los de la
versión anterior si el PR no los toca y evalúa con --base. Si cambian los casos o la rúbrica de una
funcionalidad sin cambiar su prompt, evalúa su última versión. Las carpetas que empiezan por _ son
ejemplos y se saltan.
--simulado usa prompts/<f>/simulado/ en vez de la API (para probar el circuito sin coste).
Sale con 1 si alguna versión queda bloqueada.
"""

import argparse
import pathlib
import re
import subprocess
import sys

AQUI = pathlib.Path(__file__).resolve().parent
VERSION = re.compile(r"^prompts/([^/]+)/v(\d+)\.md$")


def version(path: pathlib.Path) -> int:
    return int(path.stem[1:])


def versiones(carpeta: pathlib.Path) -> list[pathlib.Path]:
    return sorted(
        (p for p in carpeta.glob("v*.md") if re.fullmatch(r"v\d+", p.stem)), key=version
    )


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Evalúa los prompts cambiados contra su versión anterior."
    )
    ap.add_argument("--desde", default="origin/main")
    ap.add_argument("--repeticiones", type=int, default=3)
    ap.add_argument("--simulado", action="store_true")
    ap.add_argument("--raiz", default=".")
    args = ap.parse_args()
    raiz = pathlib.Path(args.raiz).resolve()

    diff = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            "--diff-filter=d",
            f"{args.desde}...HEAD",
            "--",
            "prompts/",
        ],
        cwd=raiz,
        capture_output=True,
        text=True,
        check=False,
    )
    if diff.returncode:
        print(f"❌ No puedo comparar con {args.desde}: {diff.stderr.strip()}")
        return 2
    cambiados = set(diff.stdout.split())

    candidatos: set[pathlib.Path] = set()
    for ruta in sorted(cambiados):
        partes = ruta.split("/")
        if len(partes) < 3 or partes[1].startswith("_"):
            continue
        if VERSION.match(ruta):
            candidatos.add(raiz / ruta)
        elif (
            partes[2] == "resultados"
            and len(partes) > 3
            and re.match(r"v\d+\.", partes[3])
        ):
            prompt = raiz / "prompts" / partes[1] / f"{partes[3].split('.')[0]}.md"
            # un PR que trae resultados de una versión: se regeneran, no se creen
            if prompt.exists():
                candidatos.add(prompt)
        elif partes[2] in ("casos.jsonl", "rubrica.md") and versiones(
            raiz / "prompts" / partes[1]
        ):
            candidatos.add(versiones(raiz / "prompts" / partes[1])[-1])
    if not candidatos:
        print("Ningún prompt cambiado: nada que evaluar.")
        return 0

    py, bloqueados = sys.executable, []
    for prompt in sorted(candidatos):
        rel = prompt.relative_to(raiz).as_posix()
        anteriores = [
            p for p in versiones(prompt.parent) if version(p) < version(prompt)
        ]
        base = anteriores[-1].relative_to(raiz).as_posix() if anteriores else None
        comun = ["--repeticiones", str(args.repeticiones)]
        if args.simulado:
            comun += [
                "--simulado",
                (prompt.parent / "simulado").relative_to(raiz).as_posix(),
            ]
        print(
            f"\n══ {rel}"
            + (f" contra {base}" if base else " (primera versión, sin base)")
        )
        pasos = [[py, AQUI / "generar.py", rel, *comun]]
        if base:
            resultados_base = f"prompts/{prompt.parent.name}/resultados/{pathlib.Path(base).stem}.jsonl"
            reutilizar = [] if resultados_base in cambiados else ["--reutilizar"]
            pasos.append([py, AQUI / "generar.py", base, *comun, *reutilizar])
        pasos.append(
            [py, AQUI / "evaluar.py", rel, *(["--base", base] if base else [])]
        )
        for paso in pasos:
            r = subprocess.run([str(a) for a in paso], cwd=raiz, check=False)
            if r.returncode:
                bloqueados.append(rel)
                break

    print(
        f"\n{len(candidatos)} versiones evaluadas · {len(bloqueados)} bloqueadas"
        + (f": {', '.join(bloqueados)}" if bloqueados else "")
    )
    return 1 if bloqueados else 0


if __name__ == "__main__":
    sys.exit(main())
