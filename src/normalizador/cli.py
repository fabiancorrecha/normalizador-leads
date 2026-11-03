"""Raíz de composición: lee los argumentos, conecta el pipeline con sus adaptadores y lo ejecuta.

Códigos de salida: 0, carga completa; 1, configuración o export que no sirven (no se escribe nada);
2, argumentos incorrectos.
"""

# Lo exige tests/test_kit.py en todo módulo con uniones `X | None` en las anotaciones.
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import logging
import os
import pathlib
import re
import sys
from datetime import UTC, datetime

import anthropic

from normalizador.adaptadores.configuracion import (
    ConfiguracionNoValida,
    cargar_diccionario,
    cargar_perfil,
)
from normalizador.adaptadores.escritor import EscritorDeArchivos
from normalizador.adaptadores.extractor_llm import EXTRACCION_RESPALDO, ExtractorConClaude, Prompt
from normalizador.adaptadores.historico_jsonl import HistoricoIlegible, HistoricoJsonl
from normalizador.adaptadores.lector_json import LectorJson
from normalizador.aplicacion.pipeline import Pipeline
from normalizador.aplicacion.puertos import ExportIlegible, Extractor
from normalizador.dominio.diccionario import Diccionario
from normalizador.dominio.enmascarado import ReglasDeEnmascarado
from normalizador.dominio.extraccion import ExtractorPorDiccionario, ReglasDeExtraccion

logger = logging.getLogger("normalizador")

CARPETA_DE_CONFIG = pathlib.Path("config")
ARCHIVOS_DE_SECRETOS_LOCALES = (pathlib.Path(".env"), pathlib.Path(".env.dev"))
ARCHIVO_DEL_DICCIONARIO = "diccionario.yaml"
CARPETA_DE_CLINICAS = "clinicas"
IDENTIFICADOR_DE_CLINICA = re.compile(r"[a-z][a-z0-9_]*")
CARGA_FALLIDA = 1
EXTRACTOR_DICCIONARIO = "diccionario"
EXTRACTOR_CLAUDE = "claude"
PROMPT_POR_DEFECTO = pathlib.Path("prompts/extraccion-lead/v1.md")
HISTORICO_POR_DEFECTO = pathlib.Path("datos/historico_calidad.jsonl")  # fuera de git
LONGITUD_DE_LA_HUELLA = 16
TIEMPO_MAXIMO_DEL_MODELO_S = 60.0
REINTENTOS_DEL_MODELO = 2
CREDENCIALES_DEL_SDK = ("api_key", "auth_token", "credentials")  # lo que resuelve el SDK


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
        ruta_del_diccionario = opciones.config / ARCHIVO_DEL_DICCIONARIO
        diccionario = cargar_diccionario(ruta_del_diccionario)
        extractor, extraccion = componer_extractor(opciones, diccionario, ruta_del_diccionario)
        ruta_del_perfil = opciones.config / CARPETA_DE_CLINICAS / f"{opciones.clinica}.yaml"
        perfil = cargar_perfil(ruta_del_perfil, diccionario)
        huella = huella_de_la_carga(opciones.entrada, ruta_del_perfil, ruta_del_diccionario)
        huella = f"{huella}-{huella_de_la_extraccion(extraccion)}"
        pipeline = Pipeline(
            diccionario,
            perfil,
            LectorJson(),
            EscritorDeArchivos(),
            extractor,
            RelojDelSistema(),
            HistoricoJsonl(opciones.historico),
            extraccion,
        )
        resultado = pipeline.ejecutar(opciones.entrada, opciones.salida, huella)
    except (
        ConfiguracionNoValida,
        ExportIlegible,
        HistoricoIlegible,
        anthropic.AnthropicError,
    ) as error:
        return abortar(str(error))
    except OSError as error:  # la carpeta de salida o el histórico no se pueden escribir
        donde = f"{error.filename}: " if error.filename else ""
        return abortar(f"{donde}{error.strerror or error}")
    respaldos = sum(1 for aviso in resultado.avisos if aviso.codigo == EXTRACCION_RESPALDO)
    leads, cuarentena = len(resultado.leads), len(resultado.cuarentena)
    resumen = f"{leads} leads normalizados y {cuarentena} en cuarentena"
    if opciones.extractor == EXTRACTOR_CLAUDE:
        resumen += f", {respaldos} con extracción de respaldo"
    print(f"{resumen} → {opciones.salida}")
    return 0


def abortar(motivo: str) -> int:
    logger.error("carga abortada", extra={"datos": {"motivo": motivo}})
    print(f"error: {motivo}", file=sys.stderr)
    return CARGA_FALLIDA


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
    parser.add_argument(
        "--extractor",
        choices=(EXTRACTOR_DICCIONARIO, EXTRACTOR_CLAUDE),
        default=EXTRACTOR_DICCIONARIO,
        help="cómo se extraen los campos del texto: por diccionario (por defecto) o con Claude, "
        "que lee la clave de la API del entorno y cuesta dinero; nunca se activa solo por tener "
        "la clave",
    )
    parser.add_argument(
        "--modelo",
        help="modelo de Claude que sustituye al del prompt (solo con --extractor claude)",
    )
    parser.add_argument(
        "--prompt",
        type=pathlib.Path,
        default=PROMPT_POR_DEFECTO,
        help=f"versión del prompt de extracción (por defecto, {PROMPT_POR_DEFECTO})",
    )
    parser.add_argument(
        "--historico",
        type=pathlib.Path,
        default=HISTORICO_POR_DEFECTO,
        help="histórico acumulado de calidad, solo con agregados "
        f"(por defecto, {HISTORICO_POR_DEFECTO})",
    )
    return parser.parse_args(argumentos)


def huella_de_la_carga(*rutas: pathlib.Path) -> str:
    """SHA-256 del export, del perfil y del diccionario: la misma carga tiene la misma huella."""
    partes = []
    for ruta in rutas:
        try:
            partes.append(hashlib.sha256(ruta.read_bytes()).hexdigest()[:LONGITUD_DE_LA_HUELLA])
        except OSError as error:
            raise ExportIlegible(ruta, f"no se puede leer: {error.strerror}") from error
    return "-".join(partes)


def componer_extractor(
    opciones: argparse.Namespace, diccionario: Diccionario, ruta_del_diccionario: pathlib.Path
) -> tuple[Extractor, dict[str, object]]:
    """El extractor y su descripción para el informe. El de diccionario siempre existe; con
    Claude, es su respaldo (ADR-0002)."""
    reglas = reglas_de_extraccion(diccionario, ruta_del_diccionario)
    por_diccionario = ExtractorPorDiccionario(reglas)
    if opciones.extractor == EXTRACTOR_DICCIONARIO:
        return por_diccionario, {"extractor": EXTRACTOR_DICCIONARIO, "modelo": None, "prompt": None}
    enmascarado = reglas_de_enmascarado(diccionario, ruta_del_diccionario)
    prompt = cargar_prompt(opciones.prompt)
    if opciones.modelo:
        prompt = dataclasses.replace(prompt, modelo=opciones.modelo)
    for archivo in ARCHIVOS_DE_SECRETOS_LOCALES:
        cargar_secretos_locales(archivo)
    cliente = anthropic.Anthropic(
        timeout=TIEMPO_MAXIMO_DEL_MODELO_S, max_retries=REINTENTOS_DEL_MODELO
    )
    if not any(getattr(cliente, credencial, None) for credencial in CREDENCIALES_DEL_SDK):
        motivo = (
            "no hay credenciales para la API de Anthropic: define ANTHROPIC_API_KEY en el entorno "
            f"o en {' / '.join(str(a) for a in ARCHIVOS_DE_SECRETOS_LOCALES)}, o inicia sesión "
            "con `ant auth login`"
        )
        raise ConfiguracionNoValida(ARCHIVOS_DE_SECRETOS_LOCALES[0], "ANTHROPIC_API_KEY", motivo)
    con_claude = ExtractorConClaude(cliente, prompt, reglas, enmascarado, por_diccionario)
    descripcion = {
        "extractor": EXTRACTOR_CLAUDE,
        "modelo": prompt.modelo,
        "prompt": prompt.nombre,
        "huella_del_prompt": prompt.huella,
    }
    return con_claude, descripcion


def huella_de_la_extraccion(descripcion: dict[str, object]) -> str:
    """La misma carga con otro extractor, modelo o prompt es otra carga en el histórico."""
    texto = json.dumps(descripcion, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:LONGITUD_DE_LA_HUELLA]


def cargar_secretos_locales(ruta: pathlib.Path) -> None:
    """Pasa al entorno las variables de un archivo de secretos locales (`.env`, `.env.dev`) que aún
    no estén definidas; nunca las muestra. El SDK de Anthropic lee de ahí su clave."""
    if not ruta.is_file():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        nombre, valor = linea.split("=", 1)
        if nombre.strip() and valor.strip():
            os.environ.setdefault(nombre.strip(), valor.strip().strip("'\""))


def reglas_de_enmascarado(diccionario: Diccionario, ruta: pathlib.Path) -> ReglasDeEnmascarado:
    try:
        return ReglasDeEnmascarado.desde(diccionario.enmascarado)
    except ValueError as error:
        raise ConfiguracionNoValida(ruta, "enmascarado", str(error)) from error


def cargar_prompt(ruta: pathlib.Path) -> Prompt:
    try:
        return Prompt.desde_archivo(ruta)
    except (OSError, ValueError) as error:
        raise ConfiguracionNoValida(ruta, "", f"no se puede usar el prompt: {error}") from error


def reglas_de_extraccion(diccionario: Diccionario, ruta: pathlib.Path) -> ReglasDeExtraccion:
    """La sección `extraccion` la valida el dominio; su error es de configuración (REQ-NOR-018)."""
    try:
        return ReglasDeExtraccion.desde(diccionario.extraccion)
    except ValueError as error:
        raise ConfiguracionNoValida(ruta, "extraccion", str(error)) from error


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
