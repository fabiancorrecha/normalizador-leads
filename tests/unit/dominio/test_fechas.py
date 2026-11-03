"""Fechas: formatos del perfil, su zona, rango plausible y nunca adivinar (REQ-NOR-004 a 006)."""

from datetime import UTC, datetime

import pytest

from normalizador.dominio.avisos import Aviso
from normalizador.dominio.fechas import (
    LecturaDeFechas,
    RangoPlausible,
    leer_fecha,
    normalizar_fecha,
)

from .comun import EXPORT_DE_A, MADRID, MESES_ES

RANGO_DE_A = RangoPlausible(referencia=EXPORT_DE_A, dias_maximos=180)


def normalizar(valor, *formatos):
    resultado = normalizar_fecha(valor, LecturaDeFechas(formatos, MADRID, MESES_ES), RANGO_DE_A)
    return resultado.valor, resultado.avisos


def aviso(codigo):
    return (Aviso("created_at", codigo),)


@pytest.mark.parametrize(
    ("valor", "formatos"),
    [
        ("03/04/2026", ("%d/%m/%Y", "%m/%d/%Y")),
        ("25/10/2026 02:30", ("%d/%m/%Y %H:%M",)),  # se repite al atrasar el reloj
    ],
)
def test_REQ_NOR_004_fecha_con_dos_lecturas_queda_null_con_aviso(valor, formatos):
    assert normalizar(valor, *formatos) == (None, aviso("fecha_ambigua"))


@pytest.mark.parametrize(
    ("valor", "formatos"),
    [
        ("ayer", ("%d/%m/%Y", "%Y-%m-%d")),
        ("2026/13/45", ("%d/%m/%Y", "%Y-%m-%d")),
        ("32/10/2026", ("%d/%m/%Y", "%Y-%m-%d")),
        (True, ("%d/%m/%Y", "epoch_s")),
        (20261027, ("%d/%m/%Y",)),
        (["27/10/2026"], ("%d/%m/%Y",)),
        ("29/03/2026 02:30", ("%d/%m/%Y %H:%M",)),  # no existe al adelantar el reloj
        ("0001-01-01T00:00:00+01:00", ("iso8601",)),  # fuera del calendario al pasarla a UTC
        ("9999-12-31T23:30:00-01:00", ("iso8601",)),
    ],
)
def test_REQ_NOR_004_fecha_que_no_encaja_queda_null_con_aviso(valor, formatos):
    assert normalizar(valor, *formatos) == (None, aviso("fecha_no_reconocida"))


@pytest.mark.parametrize("valor", [None, "", "   "])
def test_REQ_NOR_004_fecha_ausente_queda_null_con_aviso_de_dato_ausente(valor):
    assert normalizar(valor, "%d/%m/%Y") == (None, aviso("dato_ausente"))


@pytest.mark.parametrize(
    ("valor", "formatos", "esperado"),
    [
        ("27/10/2026", ("%d/%m/%Y",), "2026-10-26T23:00:00Z"),  # hora de invierno (UTC+1)
        ("2026-10-21", ("%Y-%m-%d",), "2026-10-20T22:00:00Z"),  # hora de verano (UTC+2)
        ("2026-10-25", ("%Y-%m-%d",), "2026-10-24T22:00:00Z"),  # el 4424, día del cambio de hora
        ("21-oct-2026", ("%d-%b-%Y",), "2026-10-20T22:00:00Z"),  # mes en español
        ("21 de oct de 2026", ("%d de %b de %Y",), "2026-10-20T22:00:00Z"),
        (" 27/10/2026 ", ("%d/%m/%Y", "%m/%d/%Y"), "2026-10-26T23:00:00Z"),  # solo encaja dd/mm
        ("2026-10-22T09:41:00+02:00", ("iso8601",), "2026-10-22T07:41:00Z"),  # su desfase manda
        ("2026-10-26T05:03:00+06:00", ("iso8601",), "2026-10-25T23:03:00Z"),
        # El mismo instante por los dos formatos: no es ambigua.
        ("2026-10-21", ("%Y-%m-%d", "iso8601"), "2026-10-20T22:00:00Z"),
        (1761523200, ("epoch_s",), "2025-10-27T00:00:00Z"),  # el epoch no usa la zona del perfil
        ("1761523200", ("epoch_s",), "2025-10-27T00:00:00Z"),
    ],
)
def test_REQ_NOR_005_fecha_en_iso_8601_utc(valor, formatos, esperado):
    assert normalizar(valor, *formatos)[0] == esperado


def test_REQ_NOR_005_leer_fecha_da_el_instante_para_la_fecha_del_export():
    lectura = LecturaDeFechas(("%d/%m/%Y %H:%M",), MADRID)
    esperado = datetime(2026, 10, 27, 7, 14, tzinfo=UTC)

    assert leer_fecha("27/10/2026 08:14", lectura).valor == esperado


@pytest.mark.parametrize(
    ("valor", "formatos", "esperado"),
    [
        (1761523200, ("epoch_s",), "2025-10-27T00:00:00Z"),  # el 4421: un año antes del export
        ("28/10/2026", ("%d/%m/%Y",), "2026-10-27T23:00:00Z"),  # posterior al export
        ("29/04/2026", ("%d/%m/%Y",), "2026-04-28T22:00:00Z"),  # 181 días antes
    ],
)
def test_REQ_NOR_006_fecha_fuera_del_rango_se_conserva_con_aviso(valor, formatos, esperado):
    assert normalizar(valor, *formatos) == (esperado, aviso("fecha_fuera_de_rango"))


@pytest.mark.parametrize("valor", ["21/10/2026", "27/10/2026", "30/04/2026"])  # 30/04: 180 días
def test_REQ_NOR_006_fecha_dentro_del_rango_no_tiene_avisos(valor):
    assert normalizar(valor, "%d/%m/%Y")[1] == ()


@pytest.mark.parametrize(
    ("formatos", "meses"),
    [
        (("%Y-%m-%dT%H:%M:%S%z",), {}),  # el desfase se declara con iso8601
        (("%d/%m/%Y %Z",), {}),
        (("%d/%m/%Y %:z",), {}),
        (("%d/%Q/%Y",), {}),
        (("%d/%m/%Y %",), {}),
        (("fecha",), {}),
        ("%d/%m/%Y", {}),  # un texto, no una lista de formatos
        ((), {}),
        (("%d-%b-%Y",), {}),  # %b sin nombres de mes
        (("%d-%b-%Y",), {"oct": 13}),
        (("%d-%b-%Y",), {"Oct": 10, "oct": 11}),
        (("%d-%b-%Y",), {"sept.": 9}),
    ],
)
def test_REQ_NOR_018_lectura_de_fechas_mal_configurada_falla_al_crearla(formatos, meses):
    with pytest.raises(ValueError):
        LecturaDeFechas(formatos, MADRID, meses)


@pytest.mark.parametrize(
    ("referencia", "dias_maximos"),
    [
        (datetime(2026, 10, 27, 8, 14), 180),  # noqa: DTZ001 — sin zona a propósito
        (EXPORT_DE_A, 0),
        (EXPORT_DE_A, -1),
        (EXPORT_DE_A, True),
    ],
)
def test_REQ_NOR_018_rango_mal_configurado_falla_al_crearlo(referencia, dias_maximos):
    with pytest.raises(ValueError):
        RangoPlausible(referencia, dias_maximos)
