#!/usr/bin/env python3
"""Stop: Claude no puede dar la tarea por terminada si el gate de calidad falla.

Ejecuta $CLAUDE_GATE_CMD (por defecto `make check`; configúralo en .claude/settings.json).
Solo actúa si hay cambios de código: si Claude está planificando o preguntando, le deja parar.
Exit 2 = no se detiene; stderr vuelve a Claude con el motivo para que lo arregle.
"""

import json
import os
import subprocess
import sys

NO_CODIGO = ("specs/", "docs/", "README", "LEEME")


def hay_cambios_de_codigo(cwd: str) -> bool:
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if status.returncode != 0:  # no es un repo git: mejor comprobar siempre
        return True
    paths = [line[3:] for line in status.stdout.splitlines()]
    return any(not p.startswith(NO_CODIGO) and not p.endswith(".md") for p in paths)


def main() -> int:
    payload = json.load(sys.stdin)
    # Evita bucles infinitos: si ya reintentó una vez, deja parar (la CI sigue siendo el gate final).
    if payload.get("stop_hook_active"):
        return 0
    from raiz import raiz_de_trabajo

    # en un worktree de `claude -w`, el worktree; si no, el proyecto
    cwd = raiz_de_trabajo(payload)
    if not hay_cambios_de_codigo(cwd):
        return 0
    cmd = os.environ.get("CLAUDE_GATE_CMD", "make check")
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, cwd=cwd, check=False
    )
    if result.returncode != 0:
        tail = "\n".join((result.stdout + result.stderr).splitlines()[-30:])
        print(
            f"`{cmd}` falla. No des la tarea por terminada; corrige esto primero:\n{tail}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
