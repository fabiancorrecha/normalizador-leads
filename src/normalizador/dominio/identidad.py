"""Identidad del lead: identificador, nombre, país y texto original (REQ-NOR-009 a 012)."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field

import phonenumbers

from normalizador.dominio.avisos import Normalizado, esta_ausente

CAMPO_LEAD_ID = "lead_id"
CAMPO_NOMBRE = "full_name"
CAMPO_PAIS = "country"
CAMPO_TEXTO = "enquiry_text"
SIN_IDENTIFICADOR = "sin_identificador"
NOMBRE_NO_VALIDO = "nombre_no_valido"
PAIS_DESCONOCIDO = "pais_desconocido"
TEXTO_NO_VALIDO = "texto_no_valido"

CODIGO_DE_PAIS = re.compile(r"[A-Za-z]{2}")
# BOM y espacio de ancho cero. El ZWNJ (U+200C) se queda: forma parte de nombres persas.
INVISIBLES_EN_LOS_EXTREMOS = "﻿​"


def construir_lead_id(source: str, id_original: object) -> Normalizado[str]:
    """`<source>:<id original>`: el perfil delante evita colisiones entre clínicas."""
    es_id = isinstance(id_original, int | str) and not isinstance(id_original, bool)
    if not es_id or esta_ausente(id_original):
        return Normalizado.con_aviso(CAMPO_LEAD_ID, SIN_IDENTIFICADOR)
    return Normalizado(f"{source}:{str(id_original).strip()}")


def normalizar_nombre(*partes: object) -> Normalizado[str]:
    """Une las partes (nombre completo, o nombre y apellidos) con un solo espacio entre palabras."""
    if any(parte is not None and not isinstance(parte, str) for parte in partes):
        return Normalizado.con_aviso(CAMPO_NOMBRE, NOMBRE_NO_VALIDO)
    palabras = [
        palabra.strip(INVISIBLES_EN_LOS_EXTREMOS)
        for parte in partes
        if isinstance(parte, str)
        for palabra in parte.split()
    ]
    visibles = [palabra for palabra in palabras if not esta_ausente(palabra)]
    if not visibles:
        return Normalizado.ausente(CAMPO_NOMBRE)
    return Normalizado(" ".join(visibles))


@dataclass(frozen=True)
class AliasDePaises:
    """Nombres de país en cualquier idioma, y los propios códigos, → ISO 3166-1 alfa-2.

    Un código se reconoce solo si es el de algún alias: el diccionario lista los países que acepta.
    Falla al crearlo si un código no es una región conocida, si un alias está vacío, si un alias
    es el código de otro país («SA», Arabia Saudí, como alias de Sudáfrica) o si una misma clave
    lleva a dos códigos.
    """

    alias: Mapping[str, str]
    por_clave: Mapping[str, str] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        por_clave: dict[str, str] = {}
        for nombre, codigo in self.alias.items():
            if not isinstance(nombre, str) or not (clave := _clave(nombre)):
                raise ValueError(f"Alias de país no válido: {nombre!r}.")
            codigo = _codigo_valido(codigo)
            if _es_region(nombre) and nombre.strip().upper() != codigo:
                raise ValueError(f"El alias {nombre!r} es el código de otro país, no de {codigo}.")
            for clave_registrada in (clave, _clave(codigo)):
                if por_clave.setdefault(clave_registrada, codigo) != codigo:
                    raise ValueError(f"El alias de país {nombre!r} lleva a dos códigos distintos.")
        object.__setattr__(self, "por_clave", por_clave)

    @classmethod
    def desde(cls, alias: Mapping[str, str]) -> AliasDePaises:
        return cls(alias)

    def codigo_de(self, nombre: str) -> str | None:
        return self.por_clave.get(_clave(nombre))


def normalizar_pais(valor: object, alias: AliasDePaises) -> Normalizado[str]:
    """Ausente o fuera del diccionario: `pais_desconocido`, como pide REQ-NOR-010."""
    codigo = alias.codigo_de(valor) if isinstance(valor, str) else None
    if codigo is None:
        return Normalizado.con_aviso(CAMPO_PAIS, PAIS_DESCONOCIDO)
    return Normalizado(codigo)


def copiar_texto_original(valor: object) -> Normalizado[str]:
    """El mensaje tal cual llegó, también vacío: es el texto que lee el equipo (REQ-NOR-012)."""
    if valor is None:
        return Normalizado.ausente(CAMPO_TEXTO)
    if isinstance(valor, str):
        return Normalizado(valor)
    return Normalizado.con_aviso(CAMPO_TEXTO, TEXTO_NO_VALIDO)


def _codigo_valido(codigo: object) -> str:
    if (
        not isinstance(codigo, str)
        or not CODIGO_DE_PAIS.fullmatch(codigo)
        or not _es_region(codigo)
    ):
        raise ValueError(f"Código de país no válido: {codigo!r} (ISO 3166-1 alfa-2).")
    return codigo.upper()


def _es_region(texto: str) -> bool:
    return texto.strip().upper() in phonenumbers.SUPPORTED_REGIONS


def sin_tildes(texto: str) -> str:
    """Quita los acentos y otras marcas (NFKD): «Líbano» → «Libano»."""
    descompuesto = unicodedata.normalize("NFKD", texto)
    return "".join(letra for letra in descompuesto if not unicodedata.combining(letra))


def _clave(nombre: str) -> str:
    """Minúsculas, sin tildes y con un solo espacio: «  Líbano » y «LIBANO» son la misma clave."""
    return " ".join(sin_tildes(nombre).casefold().split())
