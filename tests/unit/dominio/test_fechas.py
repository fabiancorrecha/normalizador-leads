"""Fechas: formatos del perfil, su zona, rango plausible y nunca adivinar (REQ-NOR-004 a 006)."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

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


def normalizar(valor, *formatos, zona=MADRID, rango=RANGO_DE_A):
    resultado = normalizar_fecha(valor, LecturaDeFechas(formatos, zona, MESES_ES), rango)
    return resultado.valor, resultado.avisos


def aviso(codigo):
    return (Aviso("created_at", codigo),)


@pytest.mark.parametrize(
    ("valor", "formatos"),
    [
        ("03/04/2026", ("%d/%m/%Y", "%m/%d/%Y")),
        ("25/10/2026 02:30", ("%d/%m/%Y %H:%M",)),  # se repite al atrasar el reloj
        ("2026-10-25T02:30", ("iso8601",)),
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
        (10**20, ("epoch_s",)),
    ],
)
def test_REQ_NOR_004_fecha_que_no_encaja_queda_null_con_aviso(valor, formatos):
    assert normalizar(valor, *formatos) == (None, aviso("fecha_no_reconocida"))


@pytest.mark.parametrize("valor", [None, "", "   ", "​"])
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
        ("27/10/2026 07:30 PM", ("%d/%m/%Y %I:%M %p",), "2026-10-27T18:30:00Z"),
        ("2026-10-22T09:41:00+02:00", ("iso8601",), "2026-10-22T07:41:00Z"),  # su desfase manda
        ("2026-10-26T05:03:00+06:00", ("iso8601",), "2026-10-25T23:03:00Z"),
        ("2026-10-21", ("iso8601",), "2026-10-20T22:00:00Z"),  # ISO sin hora: en la zona
        ("2026-10-21T10:00", ("iso8601",), "2026-10-21T08:00:00Z"),  # ISO con hora sin desfase
        # El mismo instante por los dos formatos: no es ambigua.
        ("2026-10-21", ("%Y-%m-%d", "iso8601"), "2026-10-20T22:00:00Z"),
        (1761523200, ("epoch_s",), "2025-10-27T00:00:00Z"),  # el epoch no usa la zona del perfil
        ("1761523200", ("epoch_s",), "2025-10-27T00:00:00Z"),
    ],
)
def test_REQ_NOR_005_fecha_en_iso_8601_utc(valor, formatos, esperado):
    assert normalizar(valor, *formatos)[0] == esperado


# Una fecha sin hora tiene una sola lectura aunque la medianoche no exista o se repita en su zona.
@pytest.mark.parametrize(
    ("valor", "formatos", "zona", "esperado"),
    [
        ("06/09/2026", ("%d/%m/%Y",), "America/Santiago", "2026-09-06T04:00:00Z"),
        ("2026-09-06", ("iso8601",), "America/Santiago", "2026-09-06T04:00:00Z"),
        ("01/11/2026", ("%d/%m/%Y",), "America/Havana", "2026-11-01T04:00:00Z"),
        ("2026-11-01", ("iso8601",), "America/Havana", "2026-11-01T04:00:00Z"),
    ],
)
def test_REQ_NOR_005_fecha_sin_hora_en_zona_que_cambia_el_reloj_a_medianoche(
    valor, formatos, zona, esperado
):
    assert normalizar(valor, *formatos, zona=ZoneInfo(zona))[0] == esperado


def test_REQ_NOR_005_leer_fecha_da_el_instante_para_la_fecha_del_export():
    lectura = LecturaDeFechas(("%d/%m/%Y %H:%M",), MADRID)
    esperado = datetime(2026, 10, 27, 7, 14, tzinfo=UTC)

    assert leer_fecha("27/10/2026 08:14", lectura).valor == esperado


def test_REQ_NOR_005_leer_fecha_avisa_con_el_campo_que_se_le_indica():
    lectura = LecturaDeFechas(("%d/%m/%Y %H:%M",), MADRID)

    assert leer_fecha(None, lectura, campo="exportado").avisos == (
        Aviso("exportado", "dato_ausente"),
    )


@pytest.mark.parametrize(
    ("valor", "formatos", "esperado"),
    [
        (1761523200, ("epoch_s",), "2025-10-27T00:00:00Z"),  # el 4421: un año antes del export
        ("28/10/2026", ("%d/%m/%Y",), "2026-10-27T23:00:00Z"),  # posterior al export
        ("27/10/2026 08:15", ("%d/%m/%Y %H:%M",), "2026-10-27T07:15:00Z"),  # un minuto después
        ("29/04/2026", ("%d/%m/%Y",), "2026-04-28T22:00:00Z"),  # 181 días antes
        # Un centinela que cabe en el calendario (Madrid en el año 1: hora local media −0:14:44)
        # se conserva con aviso; nunca lanza.
        ("01/01/0001", ("%d/%m/%Y",), "0001-01-01T00:14:44Z"),
    ],
)
def test_REQ_NOR_006_fecha_fuera_del_rango_se_conserva_con_aviso(valor, formatos, esperado):
    assert normalizar(valor, *formatos) == (esperado, aviso("fecha_fuera_de_rango"))


@pytest.mark.parametrize(
    ("valor", "formatos"),
    [
        ("21/10/2026", ("%d/%m/%Y",)),
        ("27/10/2026", ("%d/%m/%Y",)),
        ("27/10/2026 08:14", ("%d/%m/%Y %H:%M",)),  # el instante del export, incluido
        ("30/04/2026", ("%d/%m/%Y",)),  # justo 180 días antes
    ],
)
def test_REQ_NOR_006_fecha_dentro_del_rango_no_tiene_avisos(valor, formatos):
    assert normalizar(valor, *formatos)[1] == ()


def test_REQ_NOR_006_el_rango_cuenta_dias_de_la_clinica_aunque_la_referencia_venga_en_utc():
    rango = RangoPlausible(datetime(2026, 10, 26, 23, 30, tzinfo=UTC), 180)  # 27/10 en Madrid

    assert normalizar("29/04/2026", "%d/%m/%Y", rango=rango)[1] == aviso("fecha_fuera_de_rango")
    assert normalizar("30/04/2026", "%d/%m/%Y", rango=rango)[1] == ()


def test_REQ_NOR_018_la_lectura_acepta_cualquier_secuencia_de_formatos():
    lectura = LecturaDeFechas((formato for formato in ["%d/%m/%Y"]), MADRID)

    assert lectura.formatos == ("%d/%m/%Y",)


@pytest.mark.parametrize(
    ("formatos", "zona", "meses"),
    [
        (("%Y-%m-%dT%H:%M:%S%z",), MADRID, {}),  # el desfase se declara con iso8601
        (("%d/%m/%Y %Z",), MADRID, {}),
        (("%d/%m/%Y %:z",), MADRID, {}),
        (("%d/%Q/%Y",), MADRID, {}),
        (("%d/%m/%Y %",), MADRID, {}),
        (("fecha",), MADRID, {}),
        (("%%",), MADRID, {}),
        (("%d/%m/%Y %d",), MADRID, {}),  # directiva repetida
        (("%d %b %m %Y",), MADRID, {"oct": 10}),  # dos meses
        (("%m/%Y",), MADRID, {}),  # sin día: no se inventa
        (("%d/%m",), MADRID, {}),  # sin año
        (("%d/%m/%Y %I:%M",), MADRID, {}),  # hora de 12 sin AM/PM
        (("%d/%m/%Y %H:%M %p",), MADRID, {}),  # AM/PM con hora de 24
        ((), MADRID, {}),
        (("%d-%b-%Y",), MADRID, {}),  # %b sin nombres de mes
        (("%d-%b-%Y",), MADRID, {"oct": 13}),
        (("%d-%b-%Y",), MADRID, {"Oct": 10, "oct": 11}),
        (("%d-%b-%Y",), MADRID, {"sept.": 9}),
        (("%d/%m/%Y",), "Europe/Madrid", {}),  # la zona es una ZoneInfo, no un texto
        (42, MADRID, {}),
    ],
)
def test_REQ_NOR_018_lectura_de_fechas_mal_configurada_falla_al_crearla(formatos, zona, meses):
    with pytest.raises(ValueError):
        LecturaDeFechas(formatos, zona, meses)


def test_REQ_NOR_018_un_texto_no_vale_como_lista_de_formatos():
    with pytest.raises(ValueError, match="lista"):
        LecturaDeFechas("%d/%m/%Y", MADRID)


@pytest.mark.parametrize(
    ("referencia", "dias_maximos"),
    [
        (datetime(2026, 10, 27, 8, 14), 180),  # noqa: DTZ001 — sin zona a propósito
        ("2026-10-27", 180),
        (EXPORT_DE_A, 0),
        (EXPORT_DE_A, -1),
        (EXPORT_DE_A, True),
        (EXPORT_DE_A, 999_999),  # se sale del calendario
        (datetime(1, 1, 1, 0, 14, 44, tzinfo=UTC), 180),  # centinela de .NET como fecha del export
    ],
)
def test_REQ_NOR_018_rango_mal_configurado_falla_al_crearlo(referencia, dias_maximos):
    with pytest.raises(ValueError):
        RangoPlausible(referencia, dias_maximos)
