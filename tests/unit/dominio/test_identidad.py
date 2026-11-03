"""Identidad del lead: nombre, país, `lead_id` y texto original (REQ-NOR-009 a 012)."""

import pytest

from normalizador.dominio.avisos import Aviso
from normalizador.dominio.identidad import (
    AliasDePaises,
    construir_lead_id,
    copiar_texto_original,
    normalizar_nombre,
    normalizar_pais,
)

ALIAS = AliasDePaises.desde(
    {
        "Líbano": "LB",
        "Lebanon": "LB",
        "Rusia": "RU",
        "United Kingdom": "GB",
        "Maroc": "MA",
        "Portugal": "PT",
        "Emiratos Árabes Unidos": "AE",
        "Suecia": "SE",
    }
)


def resultado(normalizado):
    return normalizado.valor, normalizado.avisos


@pytest.mark.parametrize(
    ("partes", "esperado"),
    [
        (("  Mariam  Khoury ",), "Mariam Khoury"),
        (("Linnea", "Johansson"), "Linnea Johansson"),
        (("Sofía Narváez",), "Sofía Narváez"),
        ((" Grace ", None), "Grace"),
    ],
)
def test_REQ_NOR_009_nombre_completo_sin_espacios_sobrantes(partes, esperado):
    assert resultado(normalizar_nombre(*partes)) == (esperado, ())


@pytest.mark.parametrize("partes", [(None,), ("",), ("  ", None)])
def test_REQ_NOR_009_nombre_ausente_queda_null_con_aviso_de_dato_ausente(partes):
    assert resultado(normalizar_nombre(*partes)) == (None, (Aviso("full_name", "dato_ausente"),))


@pytest.mark.parametrize("partes", [(42,), ("Ana", ["López"])])
def test_REQ_NOR_009_nombre_con_tipo_inesperado_queda_null_con_aviso(partes):
    esperado = (None, (Aviso("full_name", "nombre_no_valido"),))

    assert resultado(normalizar_nombre(*partes)) == esperado


@pytest.mark.parametrize(
    ("pais", "esperado"),
    [
        ("Líbano", "LB"),
        ("Lebanon", "LB"),
        ("  lebanon ", "LB"),
        ("LIBANO", "LB"),  # sin tilde y en mayúsculas
        ("Maroc", "MA"),
        ("Emiratos Arabes Unidos", "AE"),
        ("SE", "SE"),  # un código se reconoce porque es el de un alias (Suecia)
        ("se", "SE"),
    ],
)
def test_REQ_NOR_010_pais_en_iso_3166_alfa_2(pais, esperado):
    assert resultado(normalizar_pais(pais, ALIAS)) == (esperado, ())


# «IT» es un código válido, pero no es el de ningún alias del diccionario de prueba.
@pytest.mark.parametrize("pais", ["Atlantis", "XX", "IT", None, "", 34])
def test_REQ_NOR_010_pais_ausente_o_desconocido_queda_null_con_aviso(pais):
    esperado = (None, (Aviso("country", "pais_desconocido"),))

    assert resultado(normalizar_pais(pais, ALIAS)) == esperado


def test_REQ_NOR_010_alias_repetidos_que_llevan_al_mismo_codigo_valen():
    alias = AliasDePaises.desde({"Lebanon": "LB", "LEBANON": "lb"})

    assert alias.codigo_de("lebanon") == "LB"


@pytest.mark.parametrize(
    "alias",
    [
        {"Reino Unido": "gb "},
        {"Reino Unido": "GBR"},
        {"España": 34},
        {"": "ES"},
        {"  ": "ES"},
        {"Sudáfrica": "ZA", "SA": "ZA", "Arabia Saudí": "SA"},  # «SA» lleva a ZA y a SA
    ],
)
def test_REQ_NOR_018_alias_de_paises_mal_configurados_fallan_al_crearlos(alias):
    with pytest.raises(ValueError):
        AliasDePaises.desde(alias)


@pytest.mark.parametrize(
    ("source", "id_original", "esperado"),
    [
        ("clinica_a", 4417, "clinica_a:4417"),
        ("clinica_a", "4419", "clinica_a:4419"),  # el 4419 llega como texto
        ("clinica_a", " 4419 ", "clinica_a:4419"),
        ("clinica_b", "CV-2026-0881", "clinica_b:CV-2026-0881"),
    ],
)
def test_REQ_NOR_011_lead_id_con_el_perfil_y_el_id_original(source, id_original, esperado):
    assert resultado(construir_lead_id(source, id_original)) == (esperado, ())


def test_REQ_NOR_011_el_mismo_id_en_dos_clinicas_no_colisiona():
    assert construir_lead_id("clinica_a", 1).valor != construir_lead_id("clinica_b", 1).valor


@pytest.mark.parametrize("id_original", [None, "", "  ", True, 4417.0, ["4417"]])
def test_REQ_NOR_011_sin_identificador_valido_queda_null_con_aviso(id_original):
    esperado = (None, (Aviso("lead_id", "sin_identificador"),))

    assert resultado(construir_lead_id("clinica_a", id_original)) == esperado


@pytest.mark.parametrize(
    "texto", ["Здравствуйте.  Говорим только по-русски.\n", "  Hola,\tquiero cita  ", ""]
)
def test_REQ_NOR_012_el_texto_original_se_copia_sin_modificar(texto):
    assert resultado(copiar_texto_original(texto)) == (texto, ())


def test_REQ_NOR_012_texto_ausente_queda_null_con_aviso_de_dato_ausente():
    esperado = (None, (Aviso("enquiry_text", "dato_ausente"),))

    assert resultado(copiar_texto_original(None)) == esperado


def test_REQ_NOR_012_texto_con_tipo_inesperado_queda_null_con_aviso():
    esperado = (None, (Aviso("enquiry_text", "texto_no_valido"),))

    assert resultado(copiar_texto_original(42)) == esperado
