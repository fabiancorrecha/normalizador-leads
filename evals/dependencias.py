#!/usr/bin/env python3
"""Audita dependencias con vulnerabilidades conocidas según los manifiestos del proyecto.

Uso: dependencias.py [--raiz DIR] [--plan]   (--plan solo muestra lo que ejecutaría)
Necesita red y la herramienta de cada ecosistema: se ejecuta en CI (`make seguridad`).
Si hay un manifiesto y falta su herramienta, falla: auditar nada en silencio no es auditar.
"""

import argparse
import pathlib
import shlex
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
# (manifiesto que lo delata, comando de auditoría, cómo instalar la herramienta)
AUDITORIAS = [
    ("requirements.txt", "pip-audit -r requirements.txt", "pip install pip-audit"),
    (
        "pyproject.toml",
        "pip-audit",
        "pip install pip-audit (audita el entorno con el proyecto instalado)",
    ),
    ("package-lock.json", "npm audit --omit=dev --audit-level=high", "viene con Node"),
    ("pnpm-lock.yaml", "pnpm audit --prod --audit-level high", "npm install -g pnpm"),
    (
        "yarn.lock",
        "yarn npm audit --environment production --severity high",
        "corepack enable",
    ),
    (
        "go.sum",
        "govulncheck ./...",
        "go install golang.org/x/vuln/cmd/govulncheck@latest",
    ),
    ("Cargo.lock", "cargo audit", "cargo install cargo-audit"),
    ("Gemfile.lock", "bundle-audit check --update", "gem install bundler-audit"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raiz", type=pathlib.Path, default=ROOT)
    ap.add_argument("--plan", action="store_true")
    args = ap.parse_args()
    raiz = args.raiz.resolve()

    pendientes = [(m, c, i) for m, c, i in AUDITORIAS if (raiz / m).exists()]
    # requirements.txt y pyproject.toml auditan lo mismo: basta con uno.
    if any(m == "requirements.txt" for m, _, _ in pendientes):
        pendientes = [p for p in pendientes if p[0] != "pyproject.toml"]
    if not pendientes:
        print("Dependencias: no hay manifiestos reconocidos, nada que auditar.")
        return 0

    fallos = 0
    for manifiesto, comando, instalar in pendientes:
        print(f"Dependencias ({manifiesto}): {comando}")
        if args.plan:
            continue
        herramienta = shlex.split(comando)[0]
        if not shutil.which(herramienta):
            print(
                f"❌ Falta '{herramienta}' para auditar {manifiesto}. Instálala: {instalar}"
            )
            fallos += 1
            continue
        fallos += (
            subprocess.run(comando, shell=True, cwd=raiz, check=False).returncode != 0
        )
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
