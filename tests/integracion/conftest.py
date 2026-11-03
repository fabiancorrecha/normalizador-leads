"""Utilidades de integración: lanzar la CLI, exports sintéticos y configuraciones de prueba."""

# Lo exige tests/test_kit.py en todo módulo con uniones `X | None` en las anotaciones.
from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
DOCS = RAIZ / "docs"
CONFIG = RAIZ / "config"
EXPORTADO_DE_A = "27/10/2026 08:14"


def ejecutar_cli(*argumentos: str, cwd: pathlib.Path = RAIZ) -> subprocess.CompletedProcess:
    """La CLI en un proceso aparte, sin las variables ANTHROPIC_* de quien desarrolla (REC-016) y
    con un histórico temporal si el test no trae el suyo: los tests nunca tocan datos/."""
    entorno = {
        clave: valor for clave, valor in os.environ.items() if not clave.startswith("ANTHROPIC")
    }
    lista = list(argumentos)
    if "--historico" not in lista:
        temporal = pathlib.Path(tempfile.mkdtemp(prefix="historico-"))
        lista += ["--historico", str(temporal / "historico.jsonl")]
    return subprocess.run(
        [sys.executable, "-m", "normalizador", *lista],
        capture_output=True,
        text=True,
        cwd=cwd,
        env=entorno,
        check=False,
        timeout=60,
    )


def escribir_export(ruta: pathlib.Path, registros: object, exportado: str | None = EXPORTADO_DE_A):
    """Un export con la estructura de la clínica A (`registros` dentro de un objeto)."""
    export = {"centro": "Clínica de prueba", "registros": registros}
    if exportado is not None:
        export["exportado"] = exportado
    ruta.write_text(json.dumps(export, ensure_ascii=False), encoding="utf-8")
    return ruta


def leer_jsonl(ruta: pathlib.Path) -> list[dict]:
    return [json.loads(linea) for linea in ruta.read_text(encoding="utf-8").splitlines()]


def leer_json(ruta: pathlib.Path) -> dict:
    return json.loads(ruta.read_text(encoding="utf-8"))


@pytest.fixture
def config_de_prueba(tmp_path):
    """Una carpeta `config/` con el diccionario real y los perfiles que cada test escriba."""
    carpeta = tmp_path / "config"
    (carpeta / "clinicas").mkdir(parents=True)
    shutil.copy(CONFIG / "diccionario.yaml", carpeta / "diccionario.yaml")

    def con_perfil(nombre: str, contenido: str):
        (carpeta / "clinicas" / f"{nombre}.yaml").write_text(contenido, encoding="utf-8")
        return carpeta

    return con_perfil


PERFIL_COMO_A = """\
source: {source}
registros: registros
zona_horaria: Europe/Madrid
fechas:
  formatos: ["%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%d", "%d-%b-%Y", "epoch_s"]
  antiguedad_maxima_dias: 180
exportado:
  ruta: exportado
  formatos: ["%d/%m/%Y %H:%M"]
"""
