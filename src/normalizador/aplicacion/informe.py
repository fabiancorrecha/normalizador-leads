"""Los bloques de calidad e histórico del informe de una carga (REQ-NOR-028 y 029).

Reciben los agregados ya calculados y devuelven diccionarios listos para `informe.json`; nunca
llevan valores de los leads.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict

from normalizador.dominio.calidad import (
    CalidadDeCampo,
    CargaEnHistorico,
    campos_no_mapeados,
    comparar_con_acumulado,
    posibles_duplicados,
)
from normalizador.dominio.lead import Lead


def bloque_de_calidad(
    por_campo: Mapping[str, CalidadDeCampo],
    leads: Sequence[Lead],
    rutas_del_export: Iterable[str],
    rutas_mapeadas: Iterable[str | None],
) -> dict[str, object]:
    return {
        "por_campo": {campo: asdict(calidad) for campo, calidad in por_campo.items()},
        "campos_no_mapeados": list(campos_no_mapeados(rutas_del_export, rutas_mapeadas)),
        "posibles_duplicados": [asdict(duplicado) for duplicado in posibles_duplicados(leads)],
    }


def bloque_de_historico(
    perfil: str,
    por_campo: Mapping[str, CalidadDeCampo],
    anteriores: Sequence[CargaEnHistorico],
    anotada: bool | None,
) -> dict[str, object]:
    """La carga frente al acumulado; `anotada` es None cuando no hay histórico."""
    comparacion = comparar_con_acumulado(perfil, por_campo, anteriores)
    return {
        "cargas_anteriores_de_la_clinica": sum(1 for carga in anteriores if carga.perfil == perfil),
        "cargas_anteriores_en_total": len(anteriores),
        "anotada": anotada,
        "por_campo": {campo: asdict(valor) for campo, valor in comparacion.items()},
    }
