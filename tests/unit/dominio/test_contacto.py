"""Contacto: teléfono en E.164 con el país del lead y email normalizado (REQ-NOR-007 y 008)."""

import pytest

from normalizador.dominio.avisos import Aviso
from normalizador.dominio.contacto import normalizar_email, normalizar_telefono


def telefono(valor, pais):
    resultado = normalizar_telefono(valor, pais)
    return resultado.valor, resultado.avisos


def email(valor):
    resultado = normalizar_email(valor)
    return resultado.valor, resultado.avisos


@pytest.mark.parametrize(
    ("valor", "pais", "esperado"),
    [
        ("+961 3 442 118", "LB", "+9613442118"),
        ("+7 912 555 0142", "RU", "+79125550142"),
        ("+212 661 304 822", "MA", "+212661304822"),
        ("+46 70 221 9043", "SE", "+46702219043"),
        ("+880 1711 556677", "BD", "+8801711556677"),
        ("612 345 678", "ES", "+34612345678"),  # sin prefijo: se interpreta con el país del lead
        ("+52 55 4412 8890", None, "+525544128890"),  # con prefijo no hace falta el país
    ],
)
def test_REQ_NOR_007_telefono_en_e164(valor, pais, esperado):
    assert telefono(valor, pais) == (esperado, ())


@pytest.mark.parametrize(
    ("valor", "pais", "esperado"),
    [
        ("07700 900182", "GB", "+447700900182"),  # el 4419: rango británico de ficción
        ("612 345 678", "GB", "+44612345678"),  # un móvil español leído como británico
    ],
)
def test_REQ_NOR_007_telefono_posible_pero_no_asignado_se_conserva_con_aviso(valor, pais, esperado):
    assert telefono(valor, pais) == (esperado, (Aviso("phone", "telefono_no_verificado"),))


@pytest.mark.parametrize("pais", [None, "XX", "es"])  # sin país, o uno que phonenumbers no conoce
def test_REQ_NOR_007_telefono_sin_prefijo_ni_pais_queda_null_con_aviso(pais):
    assert telefono("07700 900182", pais) == (None, (Aviso("phone", "telefono_sin_region"),))


@pytest.mark.parametrize("valor", ["abc", "12", 612345678, True])
def test_REQ_NOR_007_telefono_que_no_se_puede_interpretar_queda_null_con_aviso(valor):
    assert telefono(valor, "ES") == (None, (Aviso("phone", "telefono_no_valido"),))


@pytest.mark.parametrize("valor", [None, "", "   "])
def test_REQ_NOR_007_telefono_ausente_queda_null_con_aviso_de_dato_ausente(valor):
    assert telefono(valor, "ES") == (None, (Aviso("phone", "dato_ausente"),))


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        ("MARIAM.KHOURY@example.com", "mariam.khoury@example.com"),
        ("  d.volkov@example.ru ", "d.volkov@example.ru"),
        ("john.reeves@example.co.uk", "john.reeves@example.co.uk"),
    ],
)
def test_REQ_NOR_008_email_sin_espacios_y_en_minusculas(valor, esperado):
    assert email(valor) == (esperado, ())


@pytest.mark.parametrize(
    "valor",
    [
        "no-es-un-email",
        "a@b",
        "dos@@example.com",
        "con espacio@example.com",
        "a@.example.com",
        "a@example..com",
        "a@example.com.",
        "mailto:a@example.com",
        "a@example.com​",  # espacio de ancho cero
        42,
    ],
)
def test_REQ_NOR_008_email_sin_formato_queda_null_con_aviso(valor):
    assert email(valor) == (None, (Aviso("email", "email_no_valido"),))


@pytest.mark.parametrize("valor", [None, "", "  "])
def test_REQ_NOR_008_email_ausente_queda_null_con_aviso_de_dato_ausente(valor):
    assert email(valor) == (None, (Aviso("email", "dato_ausente"),))
