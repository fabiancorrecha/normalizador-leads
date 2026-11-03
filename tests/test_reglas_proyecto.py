"""Tests de las reglas propias de este proyecto (.claude/hooks/reglas_proyecto.py).

Solo los cambian personas, igual que tests/test_guardrails.py. Por cada regla, un caso que
debe bloquearse y uno legítimo parecido que debe pasar: así se detectan también los falsos positivos.
Mientras las listas estén vacías, pytest marca estos tests como omitidos.
"""

import json
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
HOOKS = ROOT / ".claude" / "hooks"

# Ejemplo (SaaS con varios clientes): "psql -c 'ALTER TABLE pacientes DISABLE ROW LEVEL SECURITY'"
BASH_BLOQUEADOS: list[str] = []
# Ejemplo: "psql -c 'ALTER TABLE pacientes ENABLE ROW LEVEL SECURITY'"
BASH_PERMITIDOS: list[str] = []
# Ejemplo (pagos): ("src/cobros.py", "importe: float = 9.99")
ARCHIVOS_BLOQUEADOS: list[tuple[str, str]] = []
# Ejemplo: ("src/cobros.py", "importe_centimos: int = 999")
ARCHIVOS_PERMITIDOS: list[tuple[str, str]] = []


def run_hook(hook: str, payload: dict) -> int:
    return subprocess.run(
        [sys.executable, str(HOOKS / hook)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env={"CLAUDE_PROJECT_DIR": str(ROOT)},
        check=False,
    ).returncode


@pytest.mark.parametrize("command", BASH_BLOQUEADOS)
def test_regla_bash_bloquea(command):
    assert run_hook("guard_bash.py", {"tool_input": {"command": command}}) == 2


@pytest.mark.parametrize("command", BASH_PERMITIDOS)
def test_regla_bash_no_bloquea_lo_legitimo(command):
    assert run_hook("guard_bash.py", {"tool_input": {"command": command}}) == 0


@pytest.mark.parametrize("path,content", ARCHIVOS_BLOQUEADOS)
def test_regla_archivos_bloquea(path, content):
    assert (
        run_hook(
            "guard_files.py",
            {"tool_input": {"file_path": str(ROOT / path), "content": content}},
        )
        == 2
    )


@pytest.mark.parametrize("path,content", ARCHIVOS_PERMITIDOS)
def test_regla_archivos_no_bloquea_lo_legitimo(path, content):
    assert (
        run_hook(
            "guard_files.py",
            {"tool_input": {"file_path": str(ROOT / path), "content": content}},
        )
        == 0
    )
