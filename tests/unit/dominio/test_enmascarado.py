"""Enmascarado de documentos de identidad antes de enviar el texto al modelo (REQ-NOR-026)."""

import pathlib

import pytest
import yaml

from normalizador.dominio.enmascarado import ReglasDeEnmascarado, enmascarar

RAIZ = pathlib.Path(__file__).resolve().parents[3]
DICCIONARIO = yaml.safe_load((RAIZ / "config" / "diccionario.yaml").read_text(encoding="utf-8"))
REGLAS = ReglasDeEnmascarado.desde(DICCIONARIO["enmascarado"])
TEXTO_DEL_4422 = (
    "Guten Tag, ich interessiere mich für eine Augenlaserbehandlung. Ich wohne in Valencia, bin "
    "aber deutscher Staatsbürger. Kein Zeitdruck. Meine Ausweisnummer ist X-4471829-K, falls Sie "
    "die für die Anmeldung brauchen."
)


def test_REQ_NOR_026_el_nie_del_4422_se_enmascara_y_el_resto_del_texto_queda_igual():
    resultado = enmascarar(TEXTO_DEL_4422, REGLAS)

    assert "X-4471829-K" not in resultado.texto
    assert "4471829" not in resultado.texto
    assert resultado.texto == TEXTO_DEL_4422.replace("X-4471829-K", "[DOCUMENTO]")
    assert resultado.ocultados == ("nie",)


@pytest.mark.parametrize(
    ("texto", "oculto", "patron"),
    [
        ("Mi NIE es Y1234567L.", "Y1234567L", "nie"),
        ("Mi NIE es z 1234567 l.", "z 1234567 l", "nie"),
        ("DNI 12345678Z, gracias.", "12345678Z", "dni"),
        ("DNI: 12345678-Z", "12345678-Z", "dni"),
        ("Passport number AB1234567 attached.", "AB1234567", "pasaporte"),
        ("Mi pasaporte nº XDA123456 caduca pronto.", "XDA123456", "pasaporte"),
        ("Numéro de passeport: 12AB34567.", "12AB34567", "pasaporte"),
    ],
)
def test_REQ_NOR_026_cada_tipo_de_documento_se_enmascara(texto, oculto, patron):
    resultado = enmascarar(texto, REGLAS)

    assert oculto not in resultado.texto
    assert "[DOCUMENTO]" in resultado.texto
    assert patron in resultado.ocultados


@pytest.mark.parametrize(
    "texto",
    [
        "Mi teléfono es +34 612 345 678 y la cita fue el 27/10/2026.",
        "Tengo 54 años y las resonancias son de enero de 2026.",
        "Referencia CV-2026-0881, importe 1234567 euros.",
        "Call me at 07700 900182 or email john.reeves@example.co.uk",
        "",
    ],
)
def test_REQ_NOR_026_lo_que_no_es_un_documento_no_se_toca(texto):
    resultado = enmascarar(texto, REGLAS)

    assert resultado.texto == texto
    assert resultado.ocultados == ()


def test_REQ_NOR_026_varios_documentos_se_enmascaran_todos():
    resultado = enmascarar("NIE X1234567A y DNI 87654321B de mi madre.", REGLAS)

    assert resultado.texto == "NIE [DOCUMENTO] y DNI [DOCUMENTO] de mi madre."
    assert resultado.ocultados == ("nie", "dni")


def test_REQ_NOR_026_los_nombres_de_los_patrones_no_llevan_el_valor():
    resultado = enmascarar(TEXTO_DEL_4422, REGLAS)

    assert all(valor.isidentifier() for valor in resultado.ocultados)


@pytest.mark.parametrize(
    ("seccion", "campo"),
    [
        ({"documentos": {}}, "documentos"),
        ({"documentos": {"nie": "[unclosed"}}, "nie"),
        ({"documentos": {"nie": 42}}, "nie"),
        ({"documentos": {"nie": r"\d+"}, "sustituto": ""}, "sustituto"),
        ({"documentos": {"nie": r"\d+"}, "inventado": 1}, "inventado"),
        ({}, "documentos"),
    ],
)
def test_REQ_NOR_018_una_seccion_de_enmascarado_mal_configurada_falla_al_crearla(seccion, campo):
    with pytest.raises(ValueError, match=campo):
        ReglasDeEnmascarado.desde(seccion)
