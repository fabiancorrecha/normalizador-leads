"""Calidad de una carga: avisos por campo, duplicados, campos no mapeados y comparación con el
acumulado (REQ-NOR-028 y 029). Funciones puras, sin archivos."""

from dataclasses import asdict

import pytest

from normalizador.dominio.calidad import (
    CalidadDeCampo,
    CargaEnHistorico,
    Duplicado,
    calidad_por_campo,
    campos_no_mapeados,
    comparar_con_acumulado,
    posibles_duplicados,
)
from normalizador.dominio.lead import Lead

AVISOS_DE_A = [
    ("clinica_a:4419", "phone", "telefono_no_verificado"),
    ("clinica_a:4421", "phone", "origen_resuelto_por_contenido"),
    ("clinica_a:4421", "email", "dato_ausente"),
    ("clinica_a:4421", "created_at", "fecha_fuera_de_rango"),
    ("clinica_a:4422", "phone", "dato_ausente"),
    ("clinica_a:4422", "country", "pais_desconocido"),
    ("clinica_a:4423", "created_at", "fecha_ambigua"),
    ("clinica_a:4423", "phone", "dato_ausente"),
    ("clinica_a:4426", "country", "pais_desconocido"),
]


def lead(lead_id, email=None, phone=None):
    return Lead(lead_id, "clinica_a", None, email, phone, None, None, "", None, "media", None, None)


def test_REQ_NOR_028_por_campo_el_porcentaje_de_leads_con_aviso_y_sus_motivos():
    calidad = calidad_por_campo(10, AVISOS_DE_A)

    assert calidad["created_at"] == CalidadDeCampo(
        con_aviso=2, porcentaje=20.0, motivos={"fecha_ambigua": 1, "fecha_fuera_de_rango": 1}
    )
    assert calidad["phone"] == CalidadDeCampo(
        con_aviso=4,
        porcentaje=40.0,
        motivos={
            "dato_ausente": 2,
            "origen_resuelto_por_contenido": 1,
            "telefono_no_verificado": 1,
        },
    )
    assert calidad["full_name"] == CalidadDeCampo(con_aviso=0, porcentaje=0.0, motivos={})
    assert set(calidad) == {
        "lead_id",
        "source",
        "full_name",
        "email",
        "phone",
        "country",
        "created_at",
        "enquiry_text",
        "specialty",
        "urgency",
        "has_reports",
        "language",
        "extraccion",
    }


def test_REQ_NOR_028_un_lead_con_dos_avisos_en_el_mismo_campo_cuenta_una_vez():
    avisos = [("x:1", "email", "email_no_valido"), ("x:1", "email", "dato_ausente")]

    calidad = calidad_por_campo(4, avisos)

    assert calidad["email"] == CalidadDeCampo(
        con_aviso=1, porcentaje=25.0, motivos={"dato_ausente": 1, "email_no_valido": 1}
    )


def test_REQ_NOR_028_sin_leads_el_porcentaje_es_cero():
    assert calidad_por_campo(0, []).get("email") == CalidadDeCampo(0, 0.0, {})


def test_REQ_NOR_028_los_posibles_duplicados_se_marcan_por_email_y_por_telefono_sin_fusionar():
    leads = [
        lead("clinica_a:4417", "mariam.khoury@example.com", "+9613442118"),
        lead("clinica_a:4418", "d.volkov@example.ru", "+79125550142"),
        lead("clinica_a:4420", "mariam.khoury@example.com", "+9613442118"),
        lead("clinica_a:4421", None, "+212661304822"),
        lead("clinica_a:4422", "a.schmitt@example.de", None),
        lead("clinica_a:4423", None, None),
    ]

    duplicados = posibles_duplicados(leads)

    assert duplicados == (
        Duplicado("email", ("clinica_a:4417", "clinica_a:4420")),
        Duplicado("phone", ("clinica_a:4417", "clinica_a:4420")),
    )
    assert len(leads) == 6  # no se fusiona nada


def test_REQ_NOR_028_los_duplicados_no_llevan_el_valor_compartido():
    leads = [lead("x:1", "a@example.com"), lead("x:2", "a@example.com")]

    duplicado = asdict(posibles_duplicados(leads)[0])

    assert set(duplicado) == {"campo", "lead_ids"}
    assert "a@example.com" not in str(duplicado)


def test_REQ_NOR_028_los_nulos_no_son_duplicados_entre_si():
    assert posibles_duplicados([lead("x:1"), lead("x:2"), lead("x:3")]) == ()


def test_REQ_NOR_028_los_campos_del_origen_que_no_se_mapearon():
    rutas_del_export = ["id", "estado", "origen", "contacto.email", "first_name", "last_name"]
    rutas_mapeadas = ["id", "contacto.email", "first_name+last_name", None]

    assert campos_no_mapeados(rutas_del_export, rutas_mapeadas) == ("estado", "origen")


def carga(perfil, huella, leads, **con_aviso):
    por_campo = {
        campo: CalidadDeCampo(cuantos, round(100 * cuantos / leads, 1), {"x": cuantos})
        for campo, cuantos in con_aviso.items()
    }
    return CargaEnHistorico(perfil, huella, "2026-11-03T12:00:00Z", leads, leads, 0, por_campo)


def test_REQ_NOR_029_la_comparacion_con_el_acumulado_de_la_clinica_y_de_todas():
    actual = {"created_at": CalidadDeCampo(2, 20.0, {"fecha_ambigua": 2})}
    anteriores = [
        carga("clinica_a", "h1", leads=10, created_at=1),  # 10 %
        carga("clinica_a", "h2", leads=10, created_at=0),  # 0 % → acumulado de la clínica 5 %
        carga("clinica_b", "h3", leads=5, created_at=5),  # 100 % → acumulado de todas 6/25 = 24 %
    ]

    comparacion = comparar_con_acumulado("clinica_a", actual, anteriores)

    assert comparacion["created_at"].porcentaje == 20.0
    assert comparacion["created_at"].acumulado_de_la_clinica == 5.0
    assert comparacion["created_at"].acumulado_de_todas == 24.0
    assert comparacion["created_at"].diferencia_con_la_clinica == 15.0


def test_REQ_NOR_029_sin_cargas_anteriores_no_hay_acumulado():
    actual = {"email": CalidadDeCampo(1, 10.0, {"dato_ausente": 1})}

    comparacion = comparar_con_acumulado("clinica_a", actual, [])

    assert comparacion["email"].acumulado_de_la_clinica is None
    assert comparacion["email"].acumulado_de_todas is None
    assert comparacion["email"].diferencia_con_la_clinica is None


def test_REQ_NOR_029_una_carga_anterior_sin_ese_campo_cuenta_como_cero_avisos():
    actual = {"language": CalidadDeCampo(0, 0.0, {})}
    anteriores = [carga("clinica_a", "h1", leads=10, created_at=1)]

    comparacion = comparar_con_acumulado("clinica_a", actual, anteriores)

    assert comparacion["language"].acumulado_de_la_clinica == 0.0


@pytest.mark.parametrize("leads", [0, -1])
def test_REQ_NOR_029_una_entrada_del_historico_sin_leads_no_rompe_el_acumulado(leads):
    actual = {"email": CalidadDeCampo(1, 10.0, {"dato_ausente": 1})}
    anteriores = [CargaEnHistorico("clinica_a", "h", "2026-11-03T12:00:00Z", 0, leads, 0, {})]

    comparacion = comparar_con_acumulado("clinica_a", actual, anteriores)

    assert comparacion["email"].acumulado_de_la_clinica is None
