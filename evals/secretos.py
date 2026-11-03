#!/usr/bin/env python3
"""Busca secretos en los archivos del repositorio (red de seguridad del hook).

Uso: secretos.py [--raiz DIR] [--preparados]
  --preparados  revisa solo lo preparado para el commit (git add), tal como se va a commitear:
                es lo que ejecuta el pre-commit de `make hooks-git`.

Usa los mismos patrones que `.claude/hooks/guard_files.py` (una sola fuente de verdad):
el hook evita que el agente escriba secretos; esto encuentra los que llegaron por otra vía.
"""

import argparse
import importlib.util
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
# Contienen secretos falsos a propósito, para probar que los guardrails los bloquean. Se comparan por el
# final de la ruta: también cubren las copias del kit que lleva dentro la skill /kit.
EXCLUIDOS = (
    "tests/test_guardrails.py",
    "tests/test_reglas_proyecto.py",
    "tests/test_kit.py",
    "evals/agente/tareas.json",
)
# Sin git, se recorre el disco: se saltan cachés, dependencias, copias de seguridad y propuestas de /kit.
CARPETAS_IGNORADAS = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    ".pgdata",
    ".kit-backup",
    ".kit",
    "graphify-out",
}


def patrones() -> list[tuple[str, str]]:
    spec = importlib.util.spec_from_file_location(
        "guard_files", ROOT / ".claude/hooks/guard_files.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.SECRETOS


def archivos(raiz: pathlib.Path) -> list[pathlib.Path]:
    git = subprocess.run(
        ["git", "ls-files", "-co", "--exclude-standard"],
        cwd=raiz,
        capture_output=True,
        text=True,
        check=False,
    )
    if git.returncode == 0:
        return [raiz / p for p in git.stdout.splitlines()]
    return [
        p
        for p in raiz.rglob("*")
        if p.is_file() and not CARPETAS_IGNORADAS & set(p.relative_to(raiz).parts)
    ]


def contenidos(raiz: pathlib.Path):
    for f in archivos(raiz):
        if not f.is_file() or f.relative_to(raiz).as_posix().startswith(
            ".claude/worktrees/"
        ):
            continue  # cada worktree se revisa en su propia sesión
        try:
            yield f.relative_to(raiz).as_posix(), f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # binarios


def preparados(raiz: pathlib.Path):
    nombres = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"],
        cwd=raiz,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split("\0")
    for rel in filter(None, nombres):
        blob = subprocess.run(
            ["git", "show", f":{rel}"], cwd=raiz, capture_output=True, check=False
        ).stdout
        try:
            yield rel, blob.decode("utf-8")
        except UnicodeDecodeError:
            continue  # binarios


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raiz", type=pathlib.Path, default=ROOT)
    ap.add_argument("--preparados", action="store_true")
    args = ap.parse_args()
    raiz = args.raiz.resolve()
    reglas = [(re.compile(p, re.IGNORECASE), motivo) for p, motivo in patrones()]
    hallazgos = []
    for rel, texto in preparados(raiz) if args.preparados else contenidos(raiz):
        if rel.endswith(EXCLUIDOS):
            continue
        for n, linea in enumerate(texto.splitlines(), 1):
            for regex, motivo in reglas:
                if regex.search(linea):
                    hallazgos.append(f"{rel}:{n} — {motivo}")
    for h in hallazgos:
        print(f"❌ {h}")
    print(
        f"Secretos: {'ninguno encontrado ✅' if not hallazgos else f'{len(hallazgos)} hallazgo(s)'}"
    )
    if hallazgos and args.preparados:
        print(
            "Commit parado. Quita el secreto (y rótalo si llegó a salir de tu máquina) y vuelve a hacer git add."
        )
    return 1 if hallazgos else 0


if __name__ == "__main__":
    sys.exit(main())
