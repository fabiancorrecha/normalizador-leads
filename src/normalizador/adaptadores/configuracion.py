"""Carga y valida el diccionario y los perfiles de clínica (YAML) como dataclasses del dominio.

Es el único sitio que lee YAML y usa pydantic. Una configuración mala para la carga antes de
procesar ningún registro, con un error que dice el archivo y el campo (REQ-NOR-018).
"""

from __future__ import annotations

import pathlib
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from normalizador.dominio.diccionario import (
    CAMPOS_MAPEABLES,
    VALIDADORES,
    CampoMapeable,
    Diccionario,
)
from normalizador.dominio.fechas import LecturaDeFechas
from normalizador.dominio.identidad import AliasDePaises
from normalizador.dominio.mapeo import LecturaDelExportado, PerfilDeClinica

ANTIGUEDAD_MAXIMA_POR_DEFECTO = 180
FORMATO_DE_SOURCE = r"^[a-z][a-z0-9_]*$"  # es el prefijo de cada lead_id y parte de una ruta


class ConfiguracionNoValida(ValueError):
    """Dice el archivo y el campo que fallan; la CLI lo traduce a un código distinto de 0."""

    def __init__(self, archivo: str | pathlib.Path, campo: str, motivo: str) -> None:
        self.archivo = str(archivo)
        self.campo = campo
        self.motivo = motivo
        donde = f"{self.archivo}: {campo}: " if campo else f"{self.archivo}: "
        super().__init__(f"{donde}{motivo}")


Proporcion = Annotated[float, Field(ge=0, le=1)]


class _Modelo(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ModeloMapeo(_Modelo):
    peso_nombre: Proporcion
    peso_contenido: Proporcion
    umbral: Proporcion
    margen: Proporcion


class ModeloCampo(_Modelo):
    sinonimos: list[str] = Field(min_length=1)
    validador: str
    composicion: list[list[str]] = []


class ModeloDiccionario(_Modelo):
    version: int = 1
    mapeo: ModeloMapeo
    campos: dict[str, ModeloCampo]
    paises: dict[str, str] = {}
    meses: dict[str, int] = {}
    extraccion: dict[str, object] = {}
    enmascarado: dict[str, object] = {}


class ModeloFechas(_Modelo):
    formatos: list[str] = Field(min_length=1)
    antiguedad_maxima_dias: int = Field(default=ANTIGUEDAD_MAXIMA_POR_DEFECTO, ge=1)


class ModeloExportado(_Modelo):
    ruta: str = Field(min_length=1)
    formatos: list[str] = Field(min_length=1)


class ModeloPerfil(_Modelo):
    source: str = Field(pattern=FORMATO_DE_SOURCE)
    registros: str = ""
    zona_horaria: str
    fechas: ModeloFechas
    exportado: ModeloExportado | None = None
    mapeo: dict[str, str] = {}


def cargar_diccionario(ruta: str | pathlib.Path) -> Diccionario:
    modelo = _validar(ModeloDiccionario, _leer_yaml(ruta), ruta)
    campos = []
    for nombre, campo in modelo.campos.items():
        if nombre not in CAMPOS_MAPEABLES:
            motivo = f"no es un campo del esquema que salga del export: {CAMPOS_MAPEABLES}"
            raise ConfiguracionNoValida(ruta, f"campos.{nombre}", motivo)
        if campo.validador not in VALIDADORES:
            motivo = f"validador desconocido {campo.validador!r}; admitidos: {VALIDADORES}"
            raise ConfiguracionNoValida(ruta, f"campos.{nombre}.validador", motivo)
        composicion = tuple(tuple(parte) for parte in campo.composicion)
        campos.append(
            _construir(
                ruta,
                f"campos.{nombre}",
                CampoMapeable,
                nombre,
                tuple(campo.sinonimos),
                campo.validador,
                composicion,
            )
        )
    paises = _construir(ruta, "paises", AliasDePaises, modelo.paises)
    # Los meses los valida fechas.py: una lectura de prueba falla con los mismos motivos.
    _construir(ruta, "meses", LecturaDeFechas, ("%d/%m/%Y",), ZoneInfo("UTC"), modelo.meses)
    return _construir(
        ruta,
        "mapeo",
        Diccionario,
        campos=tuple(campos),
        peso_nombre=modelo.mapeo.peso_nombre,
        peso_contenido=modelo.mapeo.peso_contenido,
        umbral=modelo.mapeo.umbral,
        margen=modelo.mapeo.margen,
        paises=paises,
        meses=modelo.meses,
        extraccion=modelo.extraccion,
        enmascarado=modelo.enmascarado,
    )


def cargar_perfil(ruta: str | pathlib.Path, diccionario: Diccionario) -> PerfilDeClinica:
    modelo = _validar(ModeloPerfil, _leer_yaml(ruta), ruta)
    try:
        zona = ZoneInfo(modelo.zona_horaria)
    except (ZoneInfoNotFoundError, ValueError) as error:
        motivo = f"zona horaria desconocida: {modelo.zona_horaria!r}"
        raise ConfiguracionNoValida(ruta, "zona_horaria", motivo) from error
    formatos = tuple(modelo.fechas.formatos)
    lectura = _construir(
        ruta, "fechas.formatos", LecturaDeFechas, formatos, zona, diccionario.meses
    )
    exportado = None
    if modelo.exportado is not None:
        formatos_del_export = tuple(modelo.exportado.formatos)
        lectura_del_export = _construir(
            ruta,
            "exportado.formatos",
            LecturaDeFechas,
            formatos_del_export,
            zona,
            diccionario.meses,
        )
        exportado = LecturaDelExportado(modelo.exportado.ruta, lectura_del_export)
    for campo in modelo.mapeo:
        if campo not in CAMPOS_MAPEABLES:
            motivo = f"no es un campo del esquema que salga del export: {CAMPOS_MAPEABLES}"
            raise ConfiguracionNoValida(ruta, f"mapeo.{campo}", motivo)
    return PerfilDeClinica(
        source=modelo.source,
        ruta_registros=modelo.registros,
        lectura=lectura,
        antiguedad_maxima_dias=modelo.fechas.antiguedad_maxima_dias,
        exportado=exportado,
        mapeo_explicito=dict(modelo.mapeo),
    )


def _leer_yaml(ruta: str | pathlib.Path) -> dict[str, object]:
    try:
        texto = pathlib.Path(ruta).read_text(encoding="utf-8")
    except OSError as error:
        raise ConfiguracionNoValida(ruta, "", f"no se puede leer: {error.strerror}") from error
    try:
        datos = yaml.safe_load(texto)
    except yaml.YAMLError as error:
        raise ConfiguracionNoValida(ruta, "", f"YAML no válido: {error}") from error
    if not isinstance(datos, dict):
        motivo = "el archivo tiene que ser un objeto YAML con secciones"
        raise ConfiguracionNoValida(ruta, "", motivo)
    return datos


def _validar[M: BaseModel](
    modelo: type[M], datos: dict[str, object], ruta: str | pathlib.Path
) -> M:
    try:
        return modelo.model_validate(datos)
    except ValidationError as error:
        primero = error.errors()[0]
        campo = ".".join(str(parte) for parte in primero["loc"])
        raise ConfiguracionNoValida(ruta, campo, primero["msg"]) from error


def _construir[T](
    ruta: str | pathlib.Path, campo: str, tipo: type[T], *args: object, **kwargs: object
) -> T:
    """Construye una dataclass del dominio y convierte su ValueError en error de configuración."""
    try:
        return tipo(*args, **kwargs)
    except ValueError as error:
        raise ConfiguracionNoValida(ruta, campo, str(error)) from error
