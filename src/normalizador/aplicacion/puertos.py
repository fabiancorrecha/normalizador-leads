"""Puertos de la aplicación: lo que el pipeline necesita del exterior, como `Protocol`.

Los adaptadores los implementan (archivos, modelo de IA, reloj) y los tests usan dobles en memoria.
"""

from __future__ import annotations

import pathlib
from datetime import datetime
from typing import TYPE_CHECKING, Protocol

from normalizador.dominio.extraccion import ExtraccionDelTexto

if TYPE_CHECKING:
    from normalizador.aplicacion.pipeline import ResultadoDeCarga


class ExportIlegible(ValueError):
    """El export no se puede leer o no cumple el contrato del perfil: la carga para sin escribir."""

    def __init__(self, archivo: str | pathlib.Path, motivo: str) -> None:
        self.archivo = str(archivo)
        self.motivo = motivo
        super().__init__(f"{self.archivo}: {motivo}")


class Extractor(Protocol):
    def extraer(self, texto: str | None) -> ExtraccionDelTexto: ...


class LectorDeExport(Protocol):
    def leer(self, ruta: pathlib.Path) -> object:
        """El export decodificado; lanza `ExportIlegible` si no se puede leer."""


class Escritor(Protocol):
    def escribir(self, carpeta: pathlib.Path, resultado: ResultadoDeCarga) -> None: ...


class Reloj(Protocol):
    def ahora(self) -> datetime: ...
