"""Test de humo de la CLI: el contrato de REQ-NOR-001 de punta a punta, en un proceso aparte.

Solo con la clínica A: la B entra con su perfil en T-001-5 (`test_clinicas_sin_codigo.py`).
El test fija las claves `perfil`, `entrada` y `leads_normalizados` del informe, que las tareas
siguientes deben mantener.
"""

import json
import pathlib
import subprocess
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[2]
CAMPOS_DEL_ESQUEMA = {
    "lead_id",
    "source",
    "full_name",
    "email",
    "phone",
    "country",
    "created_at",
    "enquiry_text",
    "specialty",
    "urgency",
    "has_reports",
    "language",
}


def normalizar(
    clinica: str, entrada: pathlib.Path, salida: pathlib.Path
) -> subprocess.CompletedProcess:
    comando = [sys.executable, "-m", "normalizador", "--clinica", clinica]
    comando += ["--entrada", str(entrada), "--salida", str(salida)]
    comando += ["--historico", str(salida.parent / "historico.jsonl")]  # nunca el de datos/
    return subprocess.run(
        comando, capture_output=True, text=True, cwd=RAIZ, check=False, timeout=60
    )


def test_REQ_NOR_001_la_cli_escribe_leads_e_informe_y_sale_con_0(tmp_path):
    salida = tmp_path / "salida"

    resultado = normalizar("clinica_a", RAIZ / "docs" / "clinica_a_leads.json", salida)

    assert resultado.returncode == 0, resultado.stderr
    lineas = (salida / "leads.jsonl").read_text(encoding="utf-8").splitlines()
    assert all(set(json.loads(linea)) == CAMPOS_DEL_ESQUEMA for linea in lineas)
    informe = json.loads((salida / "informe.json").read_text(encoding="utf-8"))
    assert informe["perfil"] == "clinica_a"
    assert informe["entrada"] == "clinica_a_leads.json"
    assert informe["leads_normalizados"] == len(lineas)
