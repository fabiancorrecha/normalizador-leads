"""El diccionario semántico: qué campo de origen puede ser cada campo del esquema y su validador.

Es configuración (`config/diccionario.yaml`, ADR-0001): sinónimos en varios idiomas, composiciones
(`full_name` ← `first_name` + `last_name`), el validador de contenido de cada campo, los pesos del
reranking, los alias de países y los nombres de los meses. Cada sinónimo nuevo sirve para todas las
clínicas; una configuración mala falla al crearla (REQ-NOR-018).
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from normalizador.dominio.avisos import esta_ausente
from normalizador.dominio.contacto import normalizar_email
from normalizador.dominio.fechas import LecturaDeFechas, RangoPlausible, leer_fecha
from normalizador.dominio.identidad import (
    AliasDePaises,
    construir_lead_id,
    normalizar_nombre,
    normalizar_pais,
)

# Campos del esquema que salen del export; los demás se extraen del texto o se derivan.
CAMPOS_MAPEABLES = (
    "lead_id",
    "full_name",
    "email",
    "phone",
    "country",
    "created_at",
    "enquiry_text",
)
VALIDADORES = ("identificador", "nombre", "email", "telefono", "pais", "fecha", "texto")
PARECE_TELEFONO = re.compile(r"[+＋]?[\d\s().\-]{6,24}")
DIGITOS_DE_UN_TELEFONO = range(7, 16)
LONGITUD_MAXIMA_DE_UN_ID = 64
PALABRAS_MAXIMAS_DE_UN_NOMBRE = 6
PALABRAS_MINIMAS_DE_UN_TEXTO = 3
TOLERANCIA = 1e-9

type Validador = Callable[[object], bool]


@dataclass(frozen=True)
class CampoMapeable:
    """Un campo del esquema que sale del export: sus sinónimos, su validador de contenido y, si se
    compone de varios campos de origen, los sinónimos de cada parte."""

    nombre: str
    sinonimos: tuple[str, ...]
    validador: str
    composicion: tuple[tuple[str, ...], ...] = ()

    def __post_init__(self) -> None:
        if self.nombre not in CAMPOS_MAPEABLES:
            raise ValueError(f"{self.nombre!r} no es un campo del esquema que salga del export.")
        if self.validador not in VALIDADORES:
            raise ValueError(f"Validador desconocido para {self.nombre!r}: {self.validador!r}.")
        if not self.sinonimos or not all(_es_sinonimo(s) for s in self.sinonimos):
            raise ValueError(f"El campo {self.nombre!r} necesita sinónimos, y ninguno vacío.")
        if any(not parte or not all(_es_sinonimo(s) for s in parte) for parte in self.composicion):
            raise ValueError(f"Cada parte de la composición de {self.nombre!r} necesita sinónimos.")
        object.__setattr__(self, "sinonimos", tuple(self.sinonimos))
        object.__setattr__(self, "composicion", tuple(tuple(parte) for parte in self.composicion))


@dataclass(frozen=True)
class Diccionario:
    campos: tuple[CampoMapeable, ...]
    peso_nombre: float
    peso_contenido: float
    umbral: float
    margen: float
    paises: AliasDePaises
    meses: Mapping[str, int] = field(default_factory=dict)
    # Secciones de otros módulos, que las validan ellos: `extraccion` (dominio/extraccion.py) y
    # `enmascarado` (dominio/enmascarado.py).
    extraccion: Mapping[str, object] = field(default_factory=dict)
    enmascarado: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        proporciones = {
            "peso_nombre": self.peso_nombre,
            "peso_contenido": self.peso_contenido,
            "umbral": self.umbral,
            "margen": self.margen,
        }
        for nombre, valor in proporciones.items():
            if isinstance(valor, bool) or not isinstance(valor, int | float) or not 0 <= valor <= 1:
                raise ValueError(f"{nombre} tiene que estar entre 0 y 1: {valor!r}.")
        if abs(self.peso_nombre + self.peso_contenido - 1) > TOLERANCIA:
            raise ValueError("peso_nombre y peso_contenido tienen que sumar 1.")
        nombres = [campo.nombre for campo in self.campos]
        repetidos = sorted({nombre for nombre in nombres if nombres.count(nombre) > 1})
        if repetidos:
            raise ValueError(f"Campos repetidos en el diccionario: {repetidos}.")
        if not isinstance(self.paises, AliasDePaises):
            raise ValueError("Los alias de países tienen que ser un AliasDePaises.")
        object.__setattr__(self, "campos", tuple(self.campos))
        object.__setattr__(self, "meses", dict(self.meses))

    def campo(self, nombre: str) -> CampoMapeable:
        for campo in self.campos:
            if campo.nombre == nombre:
                return campo
        raise KeyError(nombre)


@dataclass(frozen=True)
class ReglasDeLaClinica:
    """Lo que los validadores necesitan de cada clínica: sus fechas, su rango y los países."""

    lectura: LecturaDeFechas
    rango: RangoPlausible
    paises: AliasDePaises


def validadores(reglas: ReglasDeLaClinica) -> Mapping[str, Validador]:
    """Un validador de contenido por nombre: dice si un valor de origen parece del tipo del campo.

    Son laxos con lo que se normaliza después (un teléfono sin región cuenta como teléfono) y
    estrictos con el rango de las fechas: con `epoch_s` declarado, cualquier entero sería una fecha.
    """

    def es_fecha(valor: object) -> bool:
        leida = leer_fecha(valor, reglas.lectura)
        if leida.valor is None:
            return False
        # Un entero solo cuenta como fecha dentro del rango: con `epoch_s`, cualquier id lo
        # parecería. Una fecha escrita se reconoce aunque sea antigua: el rango la avisa después.
        if isinstance(valor, int) and not isinstance(valor, bool):
            return reglas.rango.admite(leida.valor, reglas.lectura.zona)
        return True

    def es_pais(valor: object) -> bool:
        return normalizar_pais(valor, reglas.paises).valor is not None

    return {
        "identificador": _es_identificador,
        "nombre": _es_nombre,
        "email": _es_email,
        "telefono": _parece_telefono,
        "pais": es_pais,
        "fecha": es_fecha,
        "texto": _es_texto,
    }


def _es_sinonimo(valor: object) -> bool:
    return isinstance(valor, str) and bool(valor.strip())


def _es_identificador(valor: object) -> bool:
    if construir_lead_id("x", valor).valor is None:
        return False
    texto = str(valor).strip()
    return len(texto) <= LONGITUD_MAXIMA_DE_UN_ID and not any(c.isspace() for c in texto)


def _es_nombre(valor: object) -> bool:
    nombre = normalizar_nombre(valor).valor if isinstance(valor, str) else None
    if nombre is None or "@" in nombre or not any(c.isalpha() for c in nombre):
        return False
    return len(nombre.split()) <= PALABRAS_MAXIMAS_DE_UN_NOMBRE


def _es_email(valor: object) -> bool:
    return normalizar_email(valor).valor is not None


def _parece_telefono(valor: object) -> bool:
    if not isinstance(valor, str):
        return False
    texto = valor.strip()
    digitos = sum(c.isdigit() for c in texto)
    return PARECE_TELEFONO.fullmatch(texto) is not None and digitos in DIGITOS_DE_UN_TELEFONO


def _es_texto(valor: object) -> bool:
    if not isinstance(valor, str) or esta_ausente(valor):
        return False
    return len(valor.split()) >= PALABRAS_MINIMAS_DE_UN_TEXTO
