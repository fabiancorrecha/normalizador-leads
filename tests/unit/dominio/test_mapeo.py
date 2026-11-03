"""Reranking del mapeo: candidatos, umbral y margen, mapeo explícito y valores por lead.

Cubre REQ-NOR-013, REQ-NOR-014 y REQ-NOR-015.
"""

import json
import pathlib

import pytest

from normalizador.dominio.avisos import Aviso
from normalizador.dominio.diccionario import (
    CampoMapeable,
    Diccionario,
    ReglasDeLaClinica,
    validadores,
)
from normalizador.dominio.fechas import LecturaDeFechas, RangoPlausible
from normalizador.dominio.identidad import AliasDePaises
from normalizador.dominio.mapeo import aplanar, proponer_mapeo, valores_de

from .comun import EXPORT_DE_A, MADRID, MESES_ES

DOCS = pathlib.Path(__file__).resolve().parents[3] / "docs"
ALIAS = AliasDePaises(
    {
        "Líbano": "LB",
        "Lebanon": "LB",
        "Rusia": "RU",
        "United Kingdom": "GB",
        "Maroc": "MA",
        "Portugal": "PT",
        "Emiratos Árabes Unidos": "AE",
        "Suecia": "SE",
        "Italia": "IT",
        "Bangladés": "BD",
        "Polonia": "PL",
        "Nigeria": "NG",
    }
)
DICCIONARIO = Diccionario(
    campos=(
        CampoMapeable("lead_id", ("id", "ref", "identificador"), "identificador"),
        CampoMapeable(
            "full_name",
            ("nombre_completo", "nombre y apellidos", "name"),
            "nombre",
            composicion=(("first_name", "nombre"), ("last_name", "apellidos")),
        ),
        CampoMapeable("email", ("email", "mail", "correo"), "email"),
        CampoMapeable("phone", ("tel", "telefono", "mobile", "phone"), "telefono"),
        CampoMapeable("country", ("pais", "country", "residence"), "pais"),
        CampoMapeable("created_at", ("fecha_alta", "fecha", "received_at"), "fecha"),
        CampoMapeable("enquiry_text", ("mensaje", "enquiry", "message"), "texto"),
    ),
    peso_nombre=0.5,
    peso_contenido=0.5,
    umbral=0.6,
    margen=0.15,
    paises=ALIAS,
    meses=MESES_ES,
)
RANGO = RangoPlausible(referencia=EXPORT_DE_A, dias_maximos=180)
LECTURA_DE_A = LecturaDeFechas(
    ("%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%d", "%d-%b-%Y", "epoch_s"), MADRID, MESES_ES
)
VALIDADORES_DE_A = validadores(ReglasDeLaClinica(LECTURA_DE_A, RANGO, ALIAS))
VALIDADORES_DE_B = validadores(
    ReglasDeLaClinica(LecturaDeFechas(("iso8601",), MADRID), RANGO, ALIAS)
)
MAPEO_DE_REFERENCIA = {
    "clinica_a": {
        "lead_id": "id",
        "full_name": "nombre_completo",
        "email": "contacto.email",
        "phone": "contacto.tel",
        "country": "pais",
        "created_at": "fecha_alta",
        "enquiry_text": "mensaje",
    },
    "clinica_b": {
        "lead_id": "ref",
        "full_name": "first_name+last_name",
        "email": "mail",
        "phone": "mobile",
        "country": "residence",
        "created_at": "received_at",
        "enquiry_text": "enquiry",
    },
}


def registros_de(clinica):
    export = json.loads((DOCS / f"{clinica}_leads.json").read_text(encoding="utf-8"))
    return export["registros"] if clinica == "clinica_a" else export


def test_REQ_NOR_013_aplanar_da_rutas_con_punto_para_los_objetos_anidados():
    registro = {"id": 1, "contacto": {"email": "a@example.com", "tel": None}, "etiquetas": [1]}

    plano = aplanar(registro)

    assert plano == {
        "id": 1,
        "contacto.email": "a@example.com",
        "contacto.tel": None,
        "etiquetas": [1],
    }


@pytest.mark.parametrize(
    ("clinica", "validadores_de_la_clinica"),
    [("clinica_a", VALIDADORES_DE_A), ("clinica_b", VALIDADORES_DE_B)],
)
def test_REQ_NOR_013_REQ_NOR_016_el_mapeo_propuesto_coincide_con_el_de_referencia(
    clinica, validadores_de_la_clinica
):
    mapeo = proponer_mapeo(registros_de(clinica), DICCIONARIO, validadores_de_la_clinica)

    assert {campo: m.ruta for campo, m in mapeo.campos.items()} == MAPEO_DE_REFERENCIA[clinica]
    assert all(m.aviso is None and m.origen == "reranking" for m in mapeo.campos.values())


def test_REQ_NOR_013_la_puntuacion_combina_nombre_y_contenido_con_los_pesos():
    mapeo = proponer_mapeo(registros_de("clinica_a"), DICCIONARIO, VALIDADORES_DE_A)
    mejor, *otros = mapeo.campos["created_at"].candidatos

    assert mejor.ruta == "fecha_alta"
    assert mejor.nombre == 1.0
    assert mejor.contenido == pytest.approx(0.8)  # el epoch del 4421 y el 03/04 ambiguo no pasan
    assert mejor.puntuacion == pytest.approx(0.5 * 1.0 + 0.5 * 0.8)
    assert all(otro.puntuacion <= mejor.puntuacion for otro in otros)


def test_REQ_NOR_013_una_palabra_del_nombre_puntua_menos_que_el_sinonimo_exacto():
    registros = [{"correo_electronico": "a@example.com"}, {"correo_electronico": "b@example.com"}]

    mapeo = proponer_mapeo(registros, DICCIONARIO, VALIDADORES_DE_A)

    assert mapeo.campos["email"].ruta == "correo_electronico"
    assert mapeo.campos["email"].candidatos[0].nombre == pytest.approx(0.5)


def test_REQ_NOR_013_el_contacto_en_texto_del_4421_es_un_candidato_pero_no_gana():
    mapeo = proponer_mapeo(registros_de("clinica_a"), DICCIONARIO, VALIDADORES_DE_A)
    candidatos = {c.ruta: c for c in mapeo.campos["phone"].candidatos}

    assert mapeo.campos["phone"].ruta == "contacto.tel"
    assert candidatos["contacto"].contenido == 1.0  # su único valor es un teléfono
    assert candidatos["contacto"].puntuacion < DICCIONARIO.umbral


def test_REQ_NOR_014_sin_candidato_sobre_el_umbral_el_campo_queda_sin_mapear_con_aviso():
    registros = [{"x": "a@example.com"}, {"x": "b@example.com"}]  # contenido sí, nombre no

    mapeo = proponer_mapeo(registros, DICCIONARIO, VALIDADORES_DE_A)

    assert mapeo.campos["email"].ruta is None
    assert mapeo.campos["email"].aviso == "mapeo_dudoso"
    assert [c.ruta for c in mapeo.campos["email"].candidatos] == ["x"]
    assert mapeo.campos["email"].candidatos[0].puntuacion == pytest.approx(0.5)


def test_REQ_NOR_014_dos_candidatos_demasiado_parecidos_dejan_el_campo_sin_mapear():
    registros = [
        {"email": "a@example.com", "correo": "c@example.com"},
        {"email": "b@example.com", "correo": "d@example.com"},
    ]

    mapeo = proponer_mapeo(registros, DICCIONARIO, VALIDADORES_DE_A)

    assert mapeo.campos["email"].ruta is None
    assert mapeo.campos["email"].aviso == "mapeo_dudoso"
    assert {c.ruta for c in mapeo.campos["email"].candidatos} == {"email", "correo"}


def test_REQ_NOR_014_un_campo_sin_ningun_candidato_queda_sin_mapear_con_aviso():
    mapeo = proponer_mapeo([{"id": 1}, {"id": 2}], DICCIONARIO, VALIDADORES_DE_A)

    assert mapeo.campos["enquiry_text"].ruta is None
    assert mapeo.campos["enquiry_text"].aviso == "mapeo_dudoso"
    assert mapeo.campos["enquiry_text"].candidatos == ()


def test_REQ_NOR_015_el_mapeo_explicito_del_perfil_manda_sobre_el_reranking():
    mapeo = proponer_mapeo(
        registros_de("clinica_a"),
        DICCIONARIO,
        VALIDADORES_DE_A,
        mapeo_explicito={"enquiry_text": "nombre_completo"},
    )

    assert mapeo.campos["enquiry_text"].ruta == "nombre_completo"
    assert mapeo.campos["enquiry_text"].origen == "perfil"
    assert mapeo.campos["enquiry_text"].aviso is None
    assert mapeo.campos["enquiry_text"].candidatos[0].ruta == "mensaje"  # el informe lo conserva


def test_REQ_NOR_015_un_mapeo_explicito_a_una_ruta_sin_datos_queda_avisado():
    mapeo = proponer_mapeo(
        registros_de("clinica_a"),
        DICCIONARIO,
        VALIDADORES_DE_A,
        mapeo_explicito={"email": "contacto.correo", "full_name": "nombre+apellidos"},
    )

    assert mapeo.campos["email"].aviso == "mapeo_explicito_sin_datos"
    assert mapeo.campos["full_name"].aviso == "mapeo_explicito_sin_datos"
    assert mapeo.campos["phone"].aviso is None


def test_REQ_NOR_015_los_demas_campos_siguen_saliendo_del_reranking():
    mapeo = proponer_mapeo(
        registros_de("clinica_a"),
        DICCIONARIO,
        VALIDADORES_DE_A,
        mapeo_explicito={"country": "pais"},
    )

    assert mapeo.campos["country"].origen == "perfil"
    assert mapeo.campos["email"].origen == "reranking"
    assert mapeo.campos["email"].ruta == "contacto.email"


def test_REQ_NOR_013_valores_de_un_lead_segun_el_mapeo():
    registros = registros_de("clinica_a")
    mapeo = proponer_mapeo(registros, DICCIONARIO, VALIDADORES_DE_A)

    valores, avisos = valores_de(registros[0], mapeo, DICCIONARIO, VALIDADORES_DE_A)

    assert valores == {
        "lead_id": 4417,
        "full_name": "  Mariam  Khoury ",
        "email": "MARIAM.KHOURY@example.com",
        "phone": "+961 3 442 118",
        "country": "Líbano",
        "created_at": "27/10/2026",
        "enquiry_text": registros[0]["mensaje"],
    }
    assert avisos == ()


def test_REQ_NOR_013_el_contacto_en_texto_del_4421_se_resuelve_por_contenido():
    registros = registros_de("clinica_a")
    mapeo = proponer_mapeo(registros, DICCIONARIO, VALIDADORES_DE_A)

    valores, avisos = valores_de(registros[4], mapeo, DICCIONARIO, VALIDADORES_DE_A)

    assert valores["phone"] == "+212 661 304 822"
    assert valores["email"] is None
    assert avisos == (Aviso("phone", "origen_resuelto_por_contenido"),)


def test_REQ_NOR_013_un_campo_compuesto_devuelve_sus_partes():
    registros = registros_de("clinica_b")
    mapeo = proponer_mapeo(registros, DICCIONARIO, VALIDADORES_DE_B)

    valores, _ = valores_de(registros[0], mapeo, DICCIONARIO, VALIDADORES_DE_B)

    assert valores["full_name"] == ("Linnea", "Johansson")


def test_REQ_NOR_014_un_campo_sin_mapear_sale_null_con_aviso_en_cada_lead():
    registros = [{"id": 1}, {"id": 2}]
    mapeo = proponer_mapeo(registros, DICCIONARIO, VALIDADORES_DE_A)

    valores, avisos = valores_de(registros[0], mapeo, DICCIONARIO, VALIDADORES_DE_A)

    assert valores["email"] is None
    assert Aviso("email", "campo_sin_mapear") in avisos


def test_REQ_NOR_013_los_registros_que_no_son_objetos_no_cuentan_para_el_mapeo():
    registros = [*registros_de("clinica_b"), "basura", 42, None]

    mapeo = proponer_mapeo(registros, DICCIONARIO, VALIDADORES_DE_B)

    assert {campo: m.ruta for campo, m in mapeo.campos.items()} == MAPEO_DE_REFERENCIA["clinica_b"]


def diccionario(**cambios):
    valores = {
        "campos": DICCIONARIO.campos,
        "peso_nombre": 0.5,
        "peso_contenido": 0.5,
        "umbral": 0.6,
        "margen": 0.15,
        "paises": ALIAS,
        "meses": MESES_ES,
    }
    return Diccionario(**{**valores, **cambios})


@pytest.mark.parametrize(
    "construir",
    [
        lambda: diccionario(peso_nombre=1.5),
        lambda: diccionario(peso_nombre=-0.1),
        lambda: diccionario(peso_nombre=0.7),  # los pesos tienen que sumar 1
        lambda: diccionario(umbral=1.2),
        lambda: diccionario(margen=-1),
        lambda: CampoMapeable("codigo_postal", ("cp",), "texto"),  # campo fuera del esquema
        lambda: CampoMapeable("email", ("mail",), "correo"),  # validador desconocido
        lambda: CampoMapeable("email", (), "email"),  # sin sinónimos
        lambda: CampoMapeable("full_name", ("name",), "nombre", composicion=((),)),
        lambda: diccionario(
            campos=(
                CampoMapeable("email", ("mail",), "email"),
                CampoMapeable("email", ("correo",), "email"),  # repetido
            )
        ),
    ],
)
def test_REQ_NOR_018_un_diccionario_mal_configurado_falla_al_crearlo(construir):
    with pytest.raises(ValueError):
        construir()
