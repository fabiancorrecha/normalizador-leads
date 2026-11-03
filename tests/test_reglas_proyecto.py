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
ARCHIVOS_BLOQUEADOS: list[tuple[str, str]] = [
    # Riesgo 1: parseo de fechas que adivina
    ("src/normalizador/dominio/fechas.py", "from dateutil import parser\n"),
    ("src/normalizador/dominio/fechas.py", "import dateutil.parser\n"),
    # Riesgo 1: errores tragados
    ("src/normalizador/aplicacion/pipeline.py", "try:\n    leer()\nexcept ValueError:\n    pass\n"),
    ("src/normalizador/adaptadores/lector_json.py", "try:\n    leer()\nexcept Exception: pass\n"),
    # Riesgo 2: datos personales en logs
    ("src/normalizador/aplicacion/pipeline.py", "logger.info(f'lead {lead.email} normalizado')\n"),
    ("src/normalizador/cli.py", "logging.warning('sin fecha: %s', registro['mensaje'])\n"),
]
ARCHIVOS_PERMITIDOS: list[tuple[str, str]] = [
    # Fechas con los formatos del perfil; dateutil fuera de src/ (p. ej. en un script de análisis)
    ("src/normalizador/dominio/fechas.py", "from datetime import datetime\nvalor = datetime.strptime(texto, formato)\n"),
    ("tests/unit/dominio/test_fechas.py", "from dateutil import parser\n"),
    # El error se convierte en aviso, y una variable que empieza por «pass» no es un pass
    ("src/normalizador/aplicacion/pipeline.py", "except ValueError as error:\n    avisos.append(Aviso('fecha_no_reconocida'))\n"),
    ("src/normalizador/aplicacion/pipeline.py", "except KeyError:\n    passthrough = None\n"),
    # Logs con identificadores técnicos
    ("src/normalizador/aplicacion/pipeline.py", "logger.info('lead normalizado', extra={'lead_id': lead.lead_id})\n"),
    ("src/normalizador/cli.py", "logging.info('carga terminada', extra={'perfil': perfil, 'leads': total})\n"),
]


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
