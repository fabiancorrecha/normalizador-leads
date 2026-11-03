"""Calidad de una carga: qué campos vienen inconsistentes, cuánto y en qué clínica.

REQ-NOR-028 y 029. Todo son agregados (recuentos, porcentajes y códigos de aviso), nunca valores
de los leads: así el informe y el histórico se guardan y se comparan entre clínicas sin datos
personales.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, fields

from normalizador.dominio.lead import Lead

CAMPO_EXTRACCION = "extraccion"  # avisos que no son de un campo del esquema (`extraccion_respaldo`)
CAMPOS_DE_CALIDAD = (*(campo.name for campo in fields(Lead)), CAMPO_EXTRACCION)
CAMPOS_DE_CONTACTO = ("email", "phone")
SEPARADOR_DE_COMPOSICION = "+"
SEPARADOR_DE_RUTA = "."
DECIMALES = 1


@dataclass(frozen=True)
class CalidadDeCampo:
    con_aviso: int  # leads con al menos un aviso en el campo
    porcentaje: float  # sobre los leads normalizados de la carga
    motivos: Mapping[str, int]  # código del aviso → cuántas veces


@dataclass(frozen=True)
class Duplicado:
    campo: str
    lead_ids: tuple[str, ...]


@dataclass(frozen=True)
class CargaEnHistorico:
    """Una carga ya hecha, tal como queda en el histórico: solo agregados."""

    perfil: str
    huella: str
    fecha: str
    registros: int
    leads: int
    cuarentena: int
    por_campo: Mapping[str, CalidadDeCampo]


@dataclass(frozen=True)
class ComparacionDeCampo:
    porcentaje: float
    acumulado_de_la_clinica: float | None
    acumulado_de_todas: float | None
    diferencia_con_la_clinica: float | None


def calidad_por_campo(
    leads: int, avisos: Iterable[tuple[str, str, str]]
) -> dict[str, CalidadDeCampo]:
    """Por campo, cuántos leads tienen aviso (cada lead cuenta una vez) y con qué motivos."""
    con_aviso: dict[str, set[str]] = defaultdict(set)
    motivos: dict[str, Counter[str]] = defaultdict(Counter)
    for lead_id, campo, codigo in avisos:
        con_aviso[campo].add(lead_id)
        motivos[campo][codigo] += 1
    campos = [*CAMPOS_DE_CALIDAD, *sorted(set(con_aviso) - set(CAMPOS_DE_CALIDAD))]
    return {
        campo: CalidadDeCampo(
            con_aviso=len(con_aviso[campo]),
            porcentaje=_porcentaje(len(con_aviso[campo]), leads),
            motivos=dict(sorted(motivos[campo].items())),
        )
        for campo in campos
    }


def posibles_duplicados(leads: Iterable[Lead]) -> tuple[Duplicado, ...]:
    """Leads que comparten email o teléfono normalizados. Se marcan, nunca se fusionan."""
    lista = list(leads)
    duplicados = []
    for campo in CAMPOS_DE_CONTACTO:
        por_valor: dict[str, list[str]] = defaultdict(list)
        for lead in lista:
            valor = getattr(lead, campo)
            if valor is not None:
                por_valor[valor].append(lead.lead_id)
        duplicados.extend(
            Duplicado(campo, tuple(sorted(ids))) for ids in por_valor.values() if len(ids) > 1
        )
    return tuple(sorted(duplicados, key=lambda d: (d.campo, d.lead_ids)))


def campos_no_mapeados(
    rutas_del_export: Iterable[str], rutas_mapeadas: Iterable[str | None]
) -> tuple[str, ...]:
    """Las rutas del export que ningún campo usa, ni como parte de una composición ni como padre."""
    usadas: set[str] = set()
    for ruta in rutas_mapeadas:
        for parte in (ruta or "").split(SEPARADOR_DE_COMPOSICION):
            if parte:
                usadas.add(parte)
                usadas.add(parte.rsplit(SEPARADOR_DE_RUTA, 1)[0])
    return tuple(ruta for ruta in rutas_del_export if ruta not in usadas)


def comparar_con_acumulado(
    perfil: str,
    actual: Mapping[str, CalidadDeCampo],
    anteriores: Sequence[CargaEnHistorico],
) -> dict[str, ComparacionDeCampo]:
    """Cada campo frente al acumulado de las cargas anteriores de la clínica y de todas."""
    de_la_clinica = [carga for carga in anteriores if carga.perfil == perfil]
    comparacion = {}
    for campo, calidad in actual.items():
        acumulado = _acumulado(campo, de_la_clinica)
        diferencia = None if acumulado is None else round(calidad.porcentaje - acumulado, DECIMALES)
        comparacion[campo] = ComparacionDeCampo(
            porcentaje=calidad.porcentaje,
            acumulado_de_la_clinica=acumulado,
            acumulado_de_todas=_acumulado(campo, anteriores),
            diferencia_con_la_clinica=diferencia,
        )
    return comparacion


def _acumulado(campo: str, cargas: Sequence[CargaEnHistorico]) -> float | None:
    """% de leads con aviso en el campo sobre todas las cargas; None si no hay leads anteriores."""
    con_leads = [carga for carga in cargas if carga.leads > 0]
    leads = sum(carga.leads for carga in con_leads)
    if leads == 0:
        return None
    con_aviso = sum(
        carga.por_campo[campo].con_aviso for carga in con_leads if campo in carga.por_campo
    )
    return _porcentaje(con_aviso, leads)


def _porcentaje(parte: int, total: int) -> float:
    return round(100 * parte / total, DECIMALES) if total > 0 else 0.0
