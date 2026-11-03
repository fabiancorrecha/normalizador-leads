"""Enmascarado de documentos de identidad en la copia del texto que sale hacia el modelo.

Los patrones viven en la sección `enmascarado` de `config/diccionario.yaml`. El texto original del
lead no se toca (REQ-NOR-012): solo se enmascara lo que se envía (REQ-NOR-026), y el resultado dice
qué patrones casaron, nunca qué valores.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

SUSTITUTO_POR_DEFECTO = "[DOCUMENTO]"
CLAVES = ("documentos", "sustituto")


@dataclass(frozen=True)
class ReglasDeEnmascarado:
    patrones: Mapping[str, re.Pattern[str]]
    sustituto: str = SUSTITUTO_POR_DEFECTO

    @classmethod
    def desde(cls, seccion: Mapping[str, object]) -> ReglasDeEnmascarado:
        if not isinstance(seccion, Mapping):
            raise ValueError("enmascarado: tiene que ser un objeto con sus claves.")
        sobran = sorted(set(seccion) - set(CLAVES))
        if sobran:
            raise ValueError(f"enmascarado: sobran las claves {sobran}.")
        documentos = seccion.get("documentos")
        if not isinstance(documentos, Mapping) or not documentos:
            raise ValueError("enmascarado.documentos: hace falta al menos un patrón con nombre.")
        patrones = {nombre: _patron(nombre, patron) for nombre, patron in documentos.items()}
        sustituto = seccion.get("sustituto", SUSTITUTO_POR_DEFECTO)
        if not isinstance(sustituto, str) or not sustituto.strip():
            raise ValueError("enmascarado.sustituto: tiene que ser un texto no vacío.")
        return cls(patrones, sustituto)


@dataclass(frozen=True)
class Enmascarado:
    texto: str
    ocultados: tuple[str, ...]  # los nombres de los patrones que casaron, nunca los valores


def enmascarar(texto: str, reglas: ReglasDeEnmascarado) -> Enmascarado:
    ocultados = []
    for nombre, patron in reglas.patrones.items():
        texto, cuantos = patron.subn(reglas.sustituto, texto)
        if cuantos:
            ocultados.append(nombre)
    return Enmascarado(texto, tuple(ocultados))


def _patron(nombre: object, patron: object) -> re.Pattern[str]:
    if not isinstance(nombre, str) or not nombre.isidentifier():
        raise ValueError(f"enmascarado.documentos: el nombre {nombre!r} no es un identificador.")
    if not isinstance(patron, str) or not patron:
        raise ValueError(f"enmascarado.documentos.{nombre}: el patrón tiene que ser un texto.")
    try:
        return re.compile(patron, re.IGNORECASE)
    except re.error as error:
        motivo = f"enmascarado.documentos.{nombre}: expresión regular no válida ({error})."
        raise ValueError(motivo) from error
