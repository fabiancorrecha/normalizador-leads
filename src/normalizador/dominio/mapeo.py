"""Reranking del mapeo: qué campo de origen es cada campo del esquema, con pesos y sin adivinar.

Los candidatos salen de recorrer los registros (también los objetos anidados: `contacto.email`) y se
puntúan por el nombre (sinónimo del diccionario) y por el contenido (% de valores que pasan el
validador). Si ninguno llega al umbral, o los dos mejores quedan a menos del margen, el campo queda
sin mapear con `mapeo_dudoso` (REQ-NOR-014); el perfil puede fijar un mapeo explícito (REQ-NOR-015).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from itertools import product

from normalizador.dominio.avisos import Aviso, esta_ausente
from normalizador.dominio.diccionario import CampoMapeable, Diccionario, Validador
from normalizador.dominio.fechas import LecturaDeFechas
from normalizador.dominio.identidad import sin_tildes

MAPEO_DUDOSO = "mapeo_dudoso"
MAPEO_EXPLICITO_SIN_DATOS = "mapeo_explicito_sin_datos"  # el perfil mapea a una ruta que no existe
CAMPO_SIN_MAPEAR = "campo_sin_mapear"
ORIGEN_RESUELTO_POR_CONTENIDO = "origen_resuelto_por_contenido"
ORIGEN_RERANKING = "reranking"
ORIGEN_PERFIL = "perfil"
SEPARADOR_DE_RUTA = "."
SEPARADOR_DE_COMPOSICION = "+"
PUNTOS_SINONIMO_EXACTO = 1.0
PUNTOS_PARTE_DEL_NOMBRE = 0.5  # `correo_electronico` para el sinónimo `correo`


@dataclass(frozen=True)
class LecturaDelExportado:
    """Dónde está la fecha del export y cómo se lee: es la referencia del rango plausible."""

    ruta: str
    lectura: LecturaDeFechas


@dataclass(frozen=True)
class PerfilDeClinica:
    """Lo que el reranking no sabe por sí solo de una clínica: `config/clinicas/<source>.yaml`."""

    source: str
    ruta_registros: str  # ruta con puntos a la lista de registros; vacía si el export es la lista
    lectura: LecturaDeFechas
    antiguedad_maxima_dias: int
    exportado: LecturaDelExportado | None = None
    mapeo_explicito: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Candidato:
    ruta: str
    puntuacion: float
    nombre: float
    contenido: float


@dataclass(frozen=True)
class MapeoDeCampo:
    campo: str
    ruta: str | None
    origen: str
    candidatos: tuple[Candidato, ...]
    aviso: str | None = None


@dataclass(frozen=True)
class Mapeo:
    campos: Mapping[str, MapeoDeCampo]

    def ruta_de(self, campo: str) -> str | None:
        return self.campos[campo].ruta


def aplanar(registro: Mapping[str, object], prefijo: str = "") -> dict[str, object]:
    """Las rutas con punto de un registro: `contacto.email`. Las listas se quedan como valores."""
    plano: dict[str, object] = {}
    for clave, valor in registro.items():
        ruta = f"{prefijo}{SEPARADOR_DE_RUTA}{clave}" if prefijo else str(clave)
        if isinstance(valor, Mapping):
            plano.update(aplanar(valor, ruta))
        else:
            plano[ruta] = valor
    return plano


def proponer_mapeo(
    registros: Iterable[object],
    diccionario: Diccionario,
    validadores: Mapping[str, Validador],
    mapeo_explicito: Mapping[str, str] | None = None,
) -> Mapeo:
    """El mapeo de cada campo del esquema, con todos los candidatos para el informe."""
    planos = [aplanar(registro) for registro in registros if isinstance(registro, Mapping)]
    rutas = {ruta for plano in planos for ruta in plano}
    explicito = dict(mapeo_explicito or {})
    campos: dict[str, MapeoDeCampo] = {}
    for campo in diccionario.campos:
        candidatos = _candidatos(campo, planos, diccionario, validadores[campo.validador])
        if campo.nombre in explicito:
            ruta = explicito[campo.nombre]
            aviso = None if _existe(ruta, rutas) else MAPEO_EXPLICITO_SIN_DATOS
            campos[campo.nombre] = MapeoDeCampo(
                campo.nombre, ruta, ORIGEN_PERFIL, candidatos, aviso
            )
        else:
            campos[campo.nombre] = _elegir(campo.nombre, candidatos, diccionario)
    return Mapeo(campos)


def valores_de(
    registro: Mapping[str, object],
    mapeo: Mapeo,
    diccionario: Diccionario,
    validadores: Mapping[str, Validador],
) -> tuple[dict[str, object], tuple[Aviso, ...]]:
    """Los valores de origen de un lead según el mapeo, aún sin normalizar.

    Un campo compuesto devuelve la tupla de sus partes. Un objeto que en este registro llegó como
    texto (`contacto` en el 4421) vale como el campo hijo si pasa su validador, con aviso.
    """
    plano = aplanar(registro)
    valores: dict[str, object] = {}
    avisos: list[Aviso] = []
    for campo, mapeado in mapeo.campos.items():
        if mapeado.ruta is None:
            valores[campo] = None
            avisos.append(Aviso(campo, CAMPO_SIN_MAPEAR))
        elif SEPARADOR_DE_COMPOSICION in mapeado.ruta:
            partes = mapeado.ruta.split(SEPARADOR_DE_COMPOSICION)
            valores[campo] = tuple(plano.get(parte) for parte in partes)
        elif mapeado.ruta in plano:
            valores[campo] = plano[mapeado.ruta]
        else:
            validador = validadores[diccionario.campo(campo).validador]
            valores[campo] = _valor_del_padre(plano, mapeado.ruta, validador)
            if valores[campo] is not None:
                avisos.append(Aviso(campo, ORIGEN_RESUELTO_POR_CONTENIDO))
    return valores, tuple(avisos)


def _elegir(
    nombre: str, candidatos: tuple[Candidato, ...], diccionario: Diccionario
) -> MapeoDeCampo:
    if not candidatos or candidatos[0].puntuacion < diccionario.umbral:
        return MapeoDeCampo(nombre, None, ORIGEN_RERANKING, candidatos, MAPEO_DUDOSO)
    mejor = candidatos[0]
    if len(candidatos) > 1 and mejor.puntuacion - candidatos[1].puntuacion < diccionario.margen:
        return MapeoDeCampo(nombre, None, ORIGEN_RERANKING, candidatos, MAPEO_DUDOSO)
    return MapeoDeCampo(nombre, mejor.ruta, ORIGEN_RERANKING, candidatos)


def _candidatos(
    campo: CampoMapeable,
    planos: list[dict[str, object]],
    diccionario: Diccionario,
    validador: Validador,
) -> tuple[Candidato, ...]:
    """Cada ruta vista en algún registro y cada composición posible, puntuadas y en orden."""
    sinonimos = {_clave(sinonimo) for sinonimo in campo.sinonimos}
    rutas = sorted({ruta for plano in planos for ruta in plano})
    candidatos = []
    for ruta in rutas:
        columna = (plano[ruta] for plano in planos if ruta in plano)
        nombre = _puntuar_nombre(ruta, sinonimos)
        contenido = _puntuar_contenido(columna, validador)
        candidatos.append(_candidato(ruta, nombre, contenido, diccionario))
    for partes in _composiciones(campo, rutas):
        con_alguna_parte = (plano for plano in planos if any(parte in plano for parte in partes))
        columna = (_unir(plano, partes) for plano in con_alguna_parte)
        contenido = _puntuar_contenido(columna, validador)
        ruta = SEPARADOR_DE_COMPOSICION.join(partes)
        candidatos.append(_candidato(ruta, PUNTOS_SINONIMO_EXACTO, contenido, diccionario))
    con_puntos = [candidato for candidato in candidatos if candidato.puntuacion > 0]
    return tuple(sorted(con_puntos, key=lambda c: (-c.puntuacion, c.ruta)))


def _candidato(ruta: str, nombre: float, contenido: float, diccionario: Diccionario) -> Candidato:
    puntuacion = diccionario.peso_nombre * nombre + diccionario.peso_contenido * contenido
    return Candidato(ruta, puntuacion, nombre, contenido)


def _puntuar_nombre(ruta: str, sinonimos: set[str]) -> float:
    """Sinónimo exacto, o una parte en común (`correo_electronico` y `correo`, `nombre` y
    `nombre completo`): el contenido decide el resto."""
    segmento = _segmento(ruta)
    if segmento in sinonimos:
        return PUNTOS_SINONIMO_EXACTO
    palabras_de_sinonimos = {palabra for sinonimo in sinonimos for palabra in sinonimo.split()}
    if segmento in palabras_de_sinonimos or set(segmento.split()) & sinonimos:
        return PUNTOS_PARTE_DEL_NOMBRE
    return 0.0


def _puntuar_contenido(columna: Iterable[object], validador: Validador) -> float:
    presentes = [valor for valor in columna if not esta_ausente(valor)]
    if not presentes:
        return 0.0
    return sum(1 for valor in presentes if validador(valor)) / len(presentes)


def _composiciones(campo: CampoMapeable, rutas: list[str]) -> list[tuple[str, ...]]:
    """Las combinaciones de rutas que casan, parte a parte, con la composición del campo."""
    if not campo.composicion:
        return []
    rutas_por_parte = []
    for sinonimos_de_la_parte in campo.composicion:
        claves = {_clave(sinonimo) for sinonimo in sinonimos_de_la_parte}
        rutas_por_parte.append([ruta for ruta in rutas if _segmento(ruta) in claves])
    return list(product(*rutas_por_parte))


def _unir(plano: dict[str, object], partes: tuple[str, ...]) -> str | None:
    textos = [plano[parte] for parte in partes if isinstance(plano.get(parte), str)]
    return " ".join(texto for texto in textos if texto.strip()) or None


def _existe(ruta: str, rutas: set[str]) -> bool:
    """Una ruta explícita del perfil (o cada parte de su composición) aparece en algún registro."""
    return all(parte in rutas for parte in ruta.split(SEPARADOR_DE_COMPOSICION))


def _valor_del_padre(plano: dict[str, object], ruta: str, validador: Validador) -> object | None:
    if SEPARADOR_DE_RUTA not in ruta:
        return None
    valor = plano.get(ruta.rsplit(SEPARADOR_DE_RUTA, 1)[0])
    return valor if valor is not None and validador(valor) else None


def _segmento(ruta: str) -> str:
    """El último tramo de una ruta (`contacto.email` → `email`), ya como clave comparable."""
    return _clave(ruta.rsplit(SEPARADOR_DE_RUTA, 1)[-1])


def _clave(nombre: str) -> str:
    """Nombres de campo comparables: minúsculas, sin tildes, y `_` o `-` como espacios."""
    return " ".join(sin_tildes(nombre).casefold().replace("_", " ").replace("-", " ").split())
