"""Extracción por diccionario del texto libre: especialidad, urgencia, informes e idioma.

Es el respaldo del extractor con modelo (ADR-0002) y la base de comparación de su eval: reglas
explicables, sin red, que salen de la sección `extraccion` de `config/diccionario.yaml`. Una sección
mal formada falla al crear las reglas (REQ-NOR-018).
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from normalizador.dominio.avisos import Aviso, esta_ausente
from normalizador.dominio.lead import Urgencia

ALTA: Urgencia = "alta"
MEDIA: Urgencia = "media"
BAJA: Urgencia = "baja"
CAMPO_ESPECIALIDAD = "specialty"
CAMPO_IDIOMA = "language"
ESPECIALIDAD_AMBIGUA = "especialidad_ambigua"
IDIOMA_NO_DETECTADO = "idioma_no_detectado"

SECCIONES = ("especialidades", "urgencia", "informes", "idiomas")
NIVELES_DE_URGENCIA = ("gravedad", "alta", "baja")
RESPUESTAS_DE_INFORMES = ("no", "si")
PARTES_DE_IDIOMAS = ("alfabetos", "palabras")
LETRAS_MINIMAS_DE_UN_ALFABETO = 15
PROPORCION_MINIMA_DE_UN_ALFABETO = 0.2
PALABRAS_MINIMAS_DE_UN_IDIOMA = 2
CODIGO_DE_IDIOMA = re.compile(r"[a-z]{2}")
NO_ES_LETRA_NI_DIGITO = re.compile(r"[^\w]+|_+")

SIN_EXTRACCION_AVISOS: tuple[Aviso, ...] = ()


@dataclass(frozen=True)
class ExtraccionDelTexto:
    """Lo que se deduce del mensaje del paciente (REQ-NOR-019 a 022)."""

    specialty: str | None
    urgency: Urgencia
    has_reports: bool | None
    language: str | None
    avisos: tuple[Aviso, ...] = SIN_EXTRACCION_AVISOS


SIN_TEXTO = ExtraccionDelTexto(None, MEDIA, None, None)


@dataclass(frozen=True)
class ReglasDeExtraccion:
    """Las señales del diccionario, ya normalizadas como el texto con el que se comparan."""

    especialidades: Mapping[str, tuple[str, ...]]
    gravedad: tuple[str, ...]
    alta: tuple[str, ...]
    baja: tuple[str, ...]
    informes_no: tuple[str, ...]
    informes_si: tuple[str, ...]
    alfabetos: Mapping[str, str]
    palabras: Mapping[str, frozenset[str]]

    @classmethod
    def desde(cls, seccion: Mapping[str, object]) -> ReglasDeExtraccion:
        _exigir_claves(seccion, SECCIONES, "extraccion")
        catalogo = _mapeo(seccion["especialidades"], "extraccion.especialidades")
        especialidades = {
            str(nombre): _senales(senales, f"extraccion.especialidades.{nombre}")
            for nombre, senales in catalogo.items()
        }
        if not especialidades:
            raise ValueError("extraccion.especialidades: hace falta al menos una especialidad.")
        urgencia = _mapeo(seccion["urgencia"], "extraccion.urgencia")
        _exigir_claves(urgencia, NIVELES_DE_URGENCIA, "extraccion.urgencia")
        informes = _mapeo(seccion["informes"], "extraccion.informes")
        _exigir_claves(informes, RESPUESTAS_DE_INFORMES, "extraccion.informes")
        idiomas = _mapeo(seccion["idiomas"], "extraccion.idiomas")
        _exigir_claves(idiomas, PARTES_DE_IDIOMAS, "extraccion.idiomas")
        por_alfabeto = _mapeo(idiomas["alfabetos"], "extraccion.idiomas.alfabetos")
        alfabetos = {
            str(alfabeto).upper(): _codigo_de_idioma(codigo, "extraccion.idiomas.alfabetos")
            for alfabeto, codigo in por_alfabeto.items()
        }
        palabras = {
            _codigo_de_idioma(codigo, "extraccion.idiomas.palabras"): frozenset(
                _senales(lista, f"extraccion.idiomas.palabras.{codigo}")
            )
            for codigo, lista in _mapeo(idiomas["palabras"], "extraccion.idiomas.palabras").items()
        }
        return cls(
            especialidades=especialidades,
            gravedad=_senales(urgencia["gravedad"], "extraccion.urgencia.gravedad", vacia=True),
            alta=_senales(urgencia["alta"], "extraccion.urgencia.alta", vacia=True),
            baja=_senales(urgencia["baja"], "extraccion.urgencia.baja", vacia=True),
            informes_no=_senales(informes["no"], "extraccion.informes.no", vacia=True),
            informes_si=_senales(informes["si"], "extraccion.informes.si", vacia=True),
            alfabetos=alfabetos,
            palabras=palabras,
        )


class ExtractorPorDiccionario:
    def __init__(self, reglas: ReglasDeExtraccion) -> None:
        self.reglas = reglas

    def extraer(self, texto: str | None) -> ExtraccionDelTexto:
        if esta_ausente(texto) or not isinstance(texto, str):
            return SIN_TEXTO
        normalizado = normalizar(texto)
        palabras = normalizado.split()
        especialidad, avisos_de_especialidad = self._especialidad(normalizado, palabras)
        idioma, avisos_de_idioma = self._idioma(texto, palabras)
        return ExtraccionDelTexto(
            specialty=especialidad,
            urgency=self._urgencia(normalizado, palabras),
            has_reports=self._informes(normalizado, palabras),
            language=idioma,
            avisos=avisos_de_especialidad + avisos_de_idioma,
        )

    def _especialidad(
        self, texto: str, palabras: list[str]
    ) -> tuple[str | None, tuple[Aviso, ...]]:
        puntos = {
            nombre: sum(_coincide(senal, texto, palabras) for senal in senales)
            for nombre, senales in self.reglas.especialidades.items()
        }
        mejor = max(puntos.values(), default=0)
        if mejor == 0:
            return None, ()
        ganadoras = [nombre for nombre, valor in puntos.items() if valor == mejor]
        if len(ganadoras) > 1:
            return None, (Aviso(CAMPO_ESPECIALIDAD, ESPECIALIDAD_AMBIGUA),)
        return ganadoras[0], ()

    def _urgencia(self, texto: str, palabras: list[str]) -> Urgencia:
        """La gravedad manda; después, lo que el paciente dice de su prisa (REQ-NOR-020)."""
        if _alguna(self.reglas.gravedad, texto, palabras):
            return ALTA
        if _alguna(self.reglas.baja, texto, palabras):
            return BAJA
        if _alguna(self.reglas.alta, texto, palabras):
            return ALTA
        return MEDIA

    def _informes(self, texto: str, palabras: list[str]) -> bool | None:
        if _alguna(self.reglas.informes_no, texto, palabras):
            return False
        if _alguna(self.reglas.informes_si, texto, palabras):
            return True
        return None

    def _idioma(self, original: str, palabras: list[str]) -> tuple[str | None, tuple[Aviso, ...]]:
        letras = [caracter for caracter in original if caracter.isalpha()]
        por_alfabeto = Counter(_alfabeto(caracter) for caracter in letras)
        for alfabeto, codigo in self.reglas.alfabetos.items():
            cuantas = por_alfabeto.get(alfabeto, 0)
            proporcion = cuantas / len(letras) if letras else 0
            if cuantas >= LETRAS_MINIMAS_DE_UN_ALFABETO or (
                cuantas and proporcion >= PROPORCION_MINIMA_DE_UN_ALFABETO
            ):
                return codigo, ()
        puntos = {
            codigo: sum(1 for palabra in palabras if palabra in frecuentes)
            for codigo, frecuentes in self.reglas.palabras.items()
        }
        mejor = max(puntos.values(), default=0)
        ganadores = [codigo for codigo, valor in puntos.items() if valor == mejor]
        if mejor < PALABRAS_MINIMAS_DE_UN_IDIOMA or len(ganadores) > 1:
            return None, (Aviso(CAMPO_IDIOMA, IDIOMA_NO_DETECTADO),)
        return ganadores[0], ()


def normalizar(texto: str) -> str:
    """Minúsculas, sin tildes y con la puntuación (guiones y apóstrofos incluidos) como espacios."""
    descompuesto = unicodedata.normalize("NFKD", texto)
    sin_tildes = "".join(letra for letra in descompuesto if not unicodedata.combining(letra))
    return " ".join(NO_ES_LETRA_NI_DIGITO.sub(" ", sin_tildes.casefold()).split())


def _coincide(senal: str, texto: str, palabras: Sequence[str]) -> bool:
    if " " in senal:
        return senal in texto
    return any(palabra.startswith(senal) for palabra in palabras)


def _alguna(senales: Sequence[str], texto: str, palabras: Sequence[str]) -> bool:
    return any(_coincide(senal, texto, palabras) for senal in senales)


def _alfabeto(caracter: str) -> str:
    """El alfabeto de una letra según su nombre Unicode: LATIN, CYRILLIC, ARABIC…"""
    return unicodedata.name(caracter, "").split(" ")[0]


def _mapeo(valor: object, ruta: str) -> Mapping[str, object]:
    if not isinstance(valor, Mapping):
        raise ValueError(f"{ruta}: tiene que ser un objeto con sus claves.")
    return valor


def _exigir_claves(valor: Mapping[str, object], claves: Sequence[str], ruta: str) -> None:
    faltan = sorted(set(claves) - set(valor))
    sobran = sorted(set(valor) - set(claves))
    if faltan or sobran:
        raise ValueError(f"{ruta}: faltan las claves {faltan} y sobran {sobran}.")


def _senales(valor: object, ruta: str, vacia: bool = False) -> tuple[str, ...]:
    if isinstance(valor, str) or not isinstance(valor, Sequence):
        raise ValueError(f"{ruta}: tiene que ser una lista de señales.")
    if not valor and not vacia:
        raise ValueError(f"{ruta}: hace falta al menos una señal.")
    if not all(isinstance(senal, str) and senal.strip() for senal in valor):
        raise ValueError(f"{ruta}: cada señal es un texto no vacío.")
    return tuple(normalizar(senal) for senal in valor)


def _codigo_de_idioma(valor: object, ruta: str) -> str:
    if not isinstance(valor, str) or not CODIGO_DE_IDIOMA.fullmatch(valor):
        raise ValueError(f"{ruta}: {valor!r} no es un código ISO 639-1 (dos letras minúsculas).")
    return valor
