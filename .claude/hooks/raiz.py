"""Raíz del proyecto para los hooks, también en sesiones de worktree.

Con `claude --worktree <nombre>`, el worktree vive en .claude/worktrees/<nombre>/ del checkout principal
y los hooks siguen recibiendo CLAUDE_PROJECT_DIR = checkout principal; la carpeta en la que trabaja
Claude llega en el campo `cwd` de la entrada del hook. Sin esto, cada archivo del worktree parecería
estar dentro de .claude/ (protegido) y el gate se ejecutaría en el checkout equivocado.
"""

import os


def principal(entrada: dict) -> str:
    return os.path.realpath(
        os.environ.get("CLAUDE_PROJECT_DIR") or entrada.get("cwd") or os.getcwd()
    )


def raiz_de(ruta: str, entrada: dict) -> str:
    """Raíz del checkout que contiene `ruta`: la del worktree de Claude Code si está en uno."""
    base = principal(entrada)
    worktrees = os.path.join(base, ".claude", "worktrees") + os.sep
    actual = os.path.realpath(ruta)
    while actual.startswith(worktrees):
        # un worktree tiene un archivo .git, no una carpeta
        if os.path.isfile(os.path.join(actual, ".git")):
            return actual
        actual = os.path.dirname(actual)
    return base


def raiz_de_trabajo(entrada: dict) -> str:
    """Raíz del checkout en el que trabaja Claude ahora mismo."""
    return (
        raiz_de(entrada["cwd"], entrada) if entrada.get("cwd") else principal(entrada)
    )
