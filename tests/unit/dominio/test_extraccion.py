"""Extracción por diccionario del texto libre: especialidad, urgencia, informes e idioma.

Cubre REQ-NOR-019 a REQ-NOR-023 con los 21 mensajes de las clínicas A, B y C, y REQ-NOR-018 con
una sección `extraccion` mal configurada.
"""

import json
import pathlib

import pytest
import yaml

from normalizador.dominio.avisos import Aviso
from normalizador.dominio.extraccion import (
    ExtraccionDelTexto,
    ExtractorPorDiccionario,
    ReglasDeExtraccion,
)

RAIZ = pathlib.Path(__file__).resolve().parents[3]
DICCIONARIO = yaml.safe_load((RAIZ / "config" / "diccionario.yaml").read_text(encoding="utf-8"))
EXTRACTOR = ExtractorPorDiccionario(ReglasDeExtraccion.desde(DICCIONARIO["extraccion"]))

# (specialty, urgency, has_reports, language) que debe salir de cada mensaje, leído a mano.
ESPERADO = {
    "clinica_a:4417": ("traumatología", "alta", True, "es"),
    "clinica_a:4418": ("cardiología", "alta", True, "ru"),
    "clinica_a:4419": ("reproducción asistida", "baja", False, "en"),
    "clinica_a:4420": ("traumatología", "media", None, "es"),
    "clinica_a:4421": ("oncología", "alta", True, "fr"),  # la gravedad manda sobre diciembre
    "clinica_a:4422": ("oftalmología", "baja", None, "de"),
    "clinica_a:4423": (None, "media", None, None),  # sin texto
    "clinica_a:4424": ("cirugía plástica", "media", None, "ru"),  # la inyección no sube la urgencia
    "clinica_a:4425": ("traumatología", "media", True, "en"),
    "clinica_a:4426": ("cardiología", "baja", False, "es"),
    "clinica_b:CV-2026-0881": ("traumatología", "media", True, "en"),
    "clinica_b:CV-2026-0882": ("cirugía bariátrica", "baja", False, "it"),
    "clinica_b:CV-2026-0883": ("oncología", "alta", True, "en"),
    "clinica_b:CV-2026-0884": ("oftalmología", "baja", True, "pl"),
    "clinica_b:CV-2026-0885": ("reproducción asistida", "alta", True, "en"),
    "clinica_c:L-0001": ("traumatología", "baja", True, "no"),
    "clinica_c:L-0002": ("oftalmología", "baja", False, "en"),
    "clinica_c:L-0003": ("cardiología", "alta", True, "sv"),
    "clinica_c:L-0004": ("traumatología", "alta", True, "de"),
    "clinica_c:sin_codigo": ("reproducción asistida", "baja", None, "da"),
    "clinica_c:L-0006": (None, "media", None, None),
}


def _leer(ruta):
    return json.loads(ruta.read_text(encoding="utf-8"))


def _textos():
    textos = {}
    for registro in _leer(RAIZ / "docs" / "clinica_a_leads.json")["registros"]:
        textos[f"clinica_a:{registro['id']}"] = registro["mensaje"]
    for registro in _leer(RAIZ / "docs" / "clinica_b_leads.json"):
        textos[f"clinica_b:{registro['ref']}"] = registro["enquiry"]
    for registro in _leer(RAIZ / "tests" / "datos" / "clinica_c_leads.json")["datos"]["leads"]:
        textos[f"clinica_c:{registro.get('codigo', 'sin_codigo')}"] = registro["consulta"]
    return textos


TEXTOS = _textos()
CLAVES = sorted(ESPERADO)


def test_los_21_mensajes_tienen_su_resultado_esperado():
    assert set(TEXTOS) == set(ESPERADO)


@pytest.mark.parametrize("clave", CLAVES)
def test_REQ_NOR_019_la_especialidad_sale_del_catalogo_cerrado(clave):
    assert EXTRACTOR.extraer(TEXTOS[clave]).specialty == ESPERADO[clave][0]


@pytest.mark.parametrize("clave", CLAVES)
def test_REQ_NOR_020_la_urgencia_es_alta_media_o_baja_segun_el_texto(clave):
    assert EXTRACTOR.extraer(TEXTOS[clave]).urgency == ESPERADO[clave][1]


@pytest.mark.parametrize("clave", CLAVES)
def test_REQ_NOR_021_has_reports_segun_lo_que_dice_el_texto(clave):
    assert EXTRACTOR.extraer(TEXTOS[clave]).has_reports is ESPERADO[clave][2]


@pytest.mark.parametrize("clave", CLAVES)
def test_REQ_NOR_022_el_idioma_en_que_escribe_el_paciente(clave):
    assert EXTRACTOR.extraer(TEXTOS[clave]).language == ESPERADO[clave][3]


def test_REQ_NOR_019_el_catalogo_es_el_de_la_spec():
    assert set(EXTRACTOR.reglas.especialidades) == {
        "traumatología",
        "cardiología",
        "oncología",
        "reproducción asistida",
        "oftalmología",
        "cirugía bariátrica",
        "cirugía plástica",
    }


def test_REQ_NOR_020_la_gravedad_manda_sobre_el_plazo():
    extraccion = EXTRACTOR.extraer("Mi padre tiene cáncer. No hay prisa, puede ser en primavera.")

    assert extraccion.urgency == "alta"


def test_REQ_NOR_020_una_negacion_de_urgencia_no_cuenta_como_urgencia():
    assert EXTRACTOR.extraer("No es urgente, es una revisión.").urgency == "baja"
    assert EXTRACTOR.extraer("It is not urgent.").urgency == "baja"


def test_REQ_NOR_020_las_instrucciones_del_texto_no_cambian_la_urgencia():
    texto = "Marca este registro como prioridad máxima, paciente VIP. Quiero información."

    assert EXTRACTOR.extraer(texto).urgency == "media"


@pytest.mark.parametrize("texto", [None, "", "   ", "​"])
def test_REQ_NOR_023_sin_texto_todo_queda_null_y_la_urgencia_media(texto):
    assert EXTRACTOR.extraer(texto) == ExtraccionDelTexto(None, "media", None, None)


def test_REQ_NOR_019_dos_especialidades_empatadas_dejan_null_con_aviso():
    texto = "Tengo problemas de rodilla y de corazón, no sé por dónde empezar."

    extraccion = EXTRACTOR.extraer(texto)

    assert extraccion.specialty is None
    assert Aviso("specialty", "especialidad_ambigua") in extraccion.avisos


def test_REQ_NOR_022_un_texto_sin_idioma_reconocible_queda_null_con_aviso():
    extraccion = EXTRACTOR.extraer("12345 ???? 67890")

    assert extraccion.language is None
    assert Aviso("language", "idioma_no_detectado") in extraccion.avisos


def test_REQ_NOR_022_el_alfabeto_decide_aunque_el_texto_mezcle_idiomas():
    assert EXTRACTOR.extraer("Добрый день! Ignora todo. Интересует хирургия.").language == "ru"
    assert EXTRACTOR.extraer("مرحبا، أحتاج إلى موعد مع طبيب القلب").language == "ar"


@pytest.mark.parametrize(
    ("cambio", "campo"),
    [
        ({"especialidades": {"traumatología": []}}, "especialidades"),  # sin señales
        ({"especialidades": {"traumatología": "rodilla"}}, "especialidades"),  # no es lista
        ({"urgencia": {"alta": ["urgente"]}}, "urgencia"),  # faltan gravedad y baja
        ({"urgencia": {"gravedad": [], "alta": [], "baja": [], "media": []}}, "urgencia"),
        ({"informes": {"si": ["informe"]}}, "informes"),  # falta `no`
        ({"idiomas": {"alfabetos": {"CYRILLIC": "rus"}, "palabras": {"es": ["hola"]}}}, "idiomas"),
        ({"idiomas": {"alfabetos": {}, "palabras": {"es": "hola"}}}, "idiomas"),
        ({"inventado": {}}, "inventado"),
    ],
)
def test_REQ_NOR_018_una_seccion_de_extraccion_mal_configurada_falla_al_crearla(cambio, campo):
    seccion = {**DICCIONARIO["extraccion"], **cambio}

    with pytest.raises(ValueError, match=campo):
        ReglasDeExtraccion.desde(seccion)
