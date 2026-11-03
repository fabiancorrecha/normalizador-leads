"""Identidad del lead: identificador, nombre, país y texto original (REQ-NOR-009 a 012)."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass

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
    palabras = [palabra for parte in partes if isinstance(parte, str) for palabra in parte.split()]
    if not palabras:
        return Normalizado.ausente(CAMPO_NOMBRE)
    return Normalizado(" ".join(palabras))


@dataclass(frozen=True)
class AliasDePaises:
    """Nombres de país en cualquier idioma, y los propios códigos, → ISO 3166-1 alfa-2.

    Un código se reconoce solo si es el de algún alias: el diccionario lista los países que acepta.
    """

    por_clave: Mapping[str, str]

    @classmethod
    def desde(cls, alias: Mapping[str, str]) -> AliasDePaises:
        """Falla si un código no tiene dos letras, si un alias está vacío o si una misma clave lleva
        a dos códigos («SA» como alias de Sudáfrica choca con el código de Arabia Saudí)."""
        codigos = {_codigo_valido(codigo) for codigo in alias.values()}
        por_clave: dict[str, str] = {}
        for nombre, codigo in [*((codigo, codigo) for codigo in codigos), *alias.items()]:
            if not isinstance(nombre, str) or not (clave := _clave(nombre)):
                raise ValueError(f"Alias de país no válido: {nombre!r}.")
            if por_clave.setdefault(clave, _codigo_valido(codigo)) != _codigo_valido(codigo):
                raise ValueError(f"El alias de país {nombre!r} lleva a dos códigos distintos.")
        return cls(por_clave)

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
    if not isinstance(codigo, str) or not CODIGO_DE_PAIS.fullmatch(codigo):
        raise ValueError(f"Código de país no válido: {codigo!r} (ISO 3166-1 alfa-2).")
    return codigo.upper()


def _clave(nombre: str) -> str:
    """Minúsculas, sin tildes y con un solo espacio: «  Líbano » y «LIBANO» son la misma clave."""
    descompuesto = unicodedata.normalize("NFKD", nombre)
    sin_tildes = "".join(letra for letra in descompuesto if not unicodedata.combining(letra))
    return " ".join(sin_tildes.casefold().split())
