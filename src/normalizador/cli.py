"""Raíz de composición: lee los argumentos, conecta el pipeline con sus adaptadores y lo ejecuta.

Códigos de salida: 0, carga completa; 1, configuración o export que no sirven (no se escribe nada);
2, argumentos incorrectos.
"""

# Lo exige tests/test_kit.py en todo módulo con uniones `X | None` en las anotaciones.
from __future__ import annotations

import argparse
import json
import logging
import pathlib
import re
import sys
from datetime import UTC, datetime

from normalizador.adaptadores.configuracion import (
    ConfiguracionNoValida,
    cargar_diccionario,
    cargar_perfil,
)
from normalizador.adaptadores.escritor import EscritorDeArchivos
from normalizador.adaptadores.lector_json import LectorJson
from normalizador.aplicacion.pipeline import ExtractorNulo, Pipeline
from normalizador.aplicacion.puertos import ExportIlegible

logger = logging.getLogger("normalizador")

CARPETA_DE_CONFIG = pathlib.Path("config")
ARCHIVO_DEL_DICCIONARIO = "diccionario.yaml"
CARPETA_DE_CLINICAS = "clinicas"
IDENTIFICADOR_DE_CLINICA = re.compile(r"[a-z][a-z0-9_]*")
CARGA_FALLIDA = 1


class RelojDelSistema:
    def ahora(self) -> datetime:
        return datetime.now(UTC)


class FormatoJson(logging.Formatter):
    """Una línea JSON por registro: nivel, evento y los datos técnicos que lleve."""

    def format(self, record: logging.LogRecord) -> str:
        datos = getattr(record, "datos", {})
        linea = {"nivel": record.levelname, "evento": record.getMessage(), **datos}
        return json.dumps(linea, ensure_ascii=False)


def main(argumentos: list[str] | None = None) -> int:
    opciones = leer_argumentos(argumentos)
    configurar_logs()
    try:
        diccionario = cargar_diccionario(opciones.config / ARCHIVO_DEL_DICCIONARIO)
        ruta_del_perfil = opciones.config / CARPETA_DE_CLINICAS / f"{opciones.clinica}.yaml"
        perfil = cargar_perfil(ruta_del_perfil, diccionario)
        pipeline = Pipeline(
            diccionario,
            perfil,
            LectorJson(),
            EscritorDeArchivos(),
            ExtractorNulo(),
            RelojDelSistema(),
        )
        resultado = pipeline.ejecutar(opciones.entrada, opciones.salida)
    except (ConfiguracionNoValida, ExportIlegible) as error:
        logger.error("carga abortada", extra={"datos": {"motivo": str(error)}})
        print(f"error: {error}", file=sys.stderr)
        return CARGA_FALLIDA
    print(
        f"{len(resultado.leads)} leads normalizados y {len(resultado.cuarentena)} en cuarentena"
        f" → {opciones.salida}"
    )
    return 0


def leer_argumentos(argumentos: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="normalizador",
        description="Normaliza el export de leads de una clínica al esquema común.",
    )
    parser.add_argument(
        "--clinica",
        required=True,
        type=identificador_de_clinica,
        help="perfil de la clínica (config/clinicas/<clinica>.yaml); es el `source` de sus leads",
    )
    parser.add_argument(
        "--entrada", required=True, type=pathlib.Path, help="export de la clínica en JSON"
    )
    parser.add_argument(
        "--salida",
        required=True,
        type=pathlib.Path,
        help="carpeta donde se escriben leads.jsonl, cuarentena.jsonl e informe.json",
    )
    parser.add_argument(
        "--config",
        type=pathlib.Path,
        default=CARPETA_DE_CONFIG,
        help="carpeta con diccionario.yaml y clinicas/ (por defecto, config/)",
    )
    return parser.parse_args(argumentos)


def identificador_de_clinica(valor: str) -> str:
    """Minúsculas, dígitos y guiones bajos: es el prefijo de cada lead_id y parte de una ruta."""
    if not IDENTIFICADOR_DE_CLINICA.fullmatch(valor):
        raise argparse.ArgumentTypeError(
            f"{valor!r} no es un identificador de clínica (minúsculas, dígitos y guiones bajos)"
        )
    return valor


def configurar_logs() -> None:
    if not logger.handlers:
        salida = logging.StreamHandler(sys.stderr)
        salida.setFormatter(FormatoJson())
        logger.addHandler(salida)
    logger.setLevel(logging.INFO)
