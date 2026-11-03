"""Avisos de normalización: un dato malo del paciente nunca es una excepción, es un aviso.

Un aviso no lleva el valor que lo causó, solo el campo y un código estable: así el informe y el
histórico de calidad no repiten datos personales (docs/riesgos.md, riesgo 2).
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

DATO_AUSENTE = "dato_ausente"
# Letras que no se ven: rellenos hangul y el patrón braille en blanco. Las categorías Unicode C*
# (control, formato como el ancho cero, surrogates, uso privado y sin asignar) tampoco se ven.
LETRAS_INVISIBLES = frozenset("ᅟᅠㅤﾠ⠀")


@dataclass(frozen=True)
class Aviso:
    campo: str
    codigo: str


@dataclass(frozen=True)
class Normalizado[T]:
    """El valor normalizado (None si no vino o no se pudo normalizar) y sus avisos."""

    valor: T | None
    avisos: tuple[Aviso, ...] = ()

    @classmethod
    def con_aviso(cls, campo: str, codigo: str, valor: T | None = None) -> Normalizado[T]:
        return cls(valor, (Aviso(campo, codigo),))

    @classmethod
    def ausente(cls, campo: str) -> Normalizado[T]:
        """Un nulo con su categoría: el informe dice qué campo vino vacío."""
        return cls.con_aviso(campo, DATO_AUSENTE)


def esta_ausente(valor: object) -> bool:
    """None o un texto sin ningún carácter visible: el dato no vino, que no es venir mal."""
    return valor is None or (isinstance(valor, str) and not any(map(es_visible, valor)))


def es_visible(caracter: str) -> bool:
    return not (caracter.isspace() or es_invisible(caracter))


def es_invisible(caracter: str) -> bool:
    return unicodedata.category(caracter).startswith("C") or caracter in LETRAS_INVISIBLES


def tiene_invisibles(texto: str) -> bool:
    return any(map(es_invisible, texto))
