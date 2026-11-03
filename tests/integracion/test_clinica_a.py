"""La clínica A de punta a punta por la CLI: esquema, mapeo de referencia y leads normalizados."""

import pytest

from .conftest import DOCS, ejecutar_cli, leer_json, leer_jsonl

CAMPOS_DEL_ESQUEMA = [
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
]
MAPEO_DE_REFERENCIA_DE_A = {
    "lead_id": "id",
    "full_name": "nombre_completo",
    "email": "contacto.email",
    "phone": "contacto.tel",
    "country": "pais",
    "created_at": "fecha_alta",
    "enquiry_text": "mensaje",
}


@pytest.fixture(scope="module")
def salida_de_a(tmp_path_factory):
    salida = tmp_path_factory.mktemp("salida") / "clinica_a"
    resultado = ejecutar_cli(
        "--clinica",
        "clinica_a",
        "--entrada",
        str(DOCS / "clinica_a_leads.json"),
        "--salida",
        str(salida),
    )
    assert resultado.returncode == 0, resultado.stderr
    return salida


@pytest.fixture(scope="module")
def leads(salida_de_a):
    return {lead["lead_id"]: lead for lead in leer_jsonl(salida_de_a / "leads.jsonl")}


@pytest.fixture(scope="module")
def informe(salida_de_a):
    return leer_json(salida_de_a / "informe.json")


def test_REQ_NOR_001_cada_lead_tiene_exactamente_los_12_campos_en_orden(salida_de_a):
    lineas = leer_jsonl(salida_de_a / "leads.jsonl")

    assert len(lineas) == 10
    assert all(list(lead) == CAMPOS_DEL_ESQUEMA for lead in lineas)


def test_REQ_NOR_001_el_informe_resume_la_carga(informe):
    assert informe["perfil"] == "clinica_a"
    assert informe["entrada"] == "clinica_a_leads.json"
    assert informe["referencia"] == "2026-10-27T07:14:00Z"  # `exportado` del export, en UTC
    assert informe["registros_de_entrada"] == 10
    assert informe["leads_normalizados"] == 10
    assert informe["en_cuarentena"] == 0


def test_REQ_NOR_016_el_mapeo_de_a_coincide_con_el_de_referencia(informe):
    mapeo = {campo: datos["ruta"] for campo, datos in informe["mapeo"].items()}

    assert mapeo == MAPEO_DE_REFERENCIA_DE_A
    assert all(datos["origen"] == "reranking" for datos in informe["mapeo"].values())
    assert all(datos["aviso"] is None for datos in informe["mapeo"].values())
    assert informe["mapeo"]["phone"]["candidatos"][0]["ruta"] == "contacto.tel"


def test_REQ_NOR_001_un_lead_completo_sale_normalizado(leads):
    assert leads["clinica_a:4417"] == {
        "lead_id": "clinica_a:4417",
        "source": "clinica_a",
        "full_name": "Mariam Khoury",
        "email": "mariam.khoury@example.com",
        "phone": "+9613442118",
        "country": "LB",
        "created_at": "2026-10-26T23:00:00Z",
        "enquiry_text": leads["clinica_a:4417"]["enquiry_text"],
        "specialty": None,
        "urgency": "media",
        "has_reports": None,
        "language": None,
    }
    assert leads["clinica_a:4417"]["enquiry_text"].startswith("Buenos días. Tengo 54 años")


@pytest.mark.parametrize(
    ("lead_id", "campo", "esperado"),
    [
        ("clinica_a:4419", "lead_id", "clinica_a:4419"),  # el id llegaba como texto
        ("clinica_a:4419", "phone", "+447700900182"),  # sin prefijo, con el país del lead
        ("clinica_a:4421", "phone", "+212661304822"),  # `contacto` en texto, resuelto por contenido
        ("clinica_a:4421", "email", None),
        ("clinica_a:4421", "created_at", "2025-10-27T00:00:00Z"),  # el epoch, un año antes
        ("clinica_a:4423", "created_at", None),  # 03/04/2026: ambigua
        ("clinica_a:4423", "enquiry_text", ""),
        ("clinica_a:4426", "country", None),  # sin país en el export
        ("clinica_a:4426", "phone", "+525544128890"),
        ("clinica_a:4422", "phone", None),
    ],
)
def test_REQ_NOR_001_los_datos_dificiles_salen_segun_la_spec(leads, lead_id, campo, esperado):
    assert leads[lead_id][campo] == esperado


@pytest.mark.parametrize(
    ("lead_id", "campo", "codigo"),
    [
        ("clinica_a:4421", "phone", "origen_resuelto_por_contenido"),
        ("clinica_a:4421", "email", "dato_ausente"),
        ("clinica_a:4421", "created_at", "fecha_fuera_de_rango"),
        ("clinica_a:4423", "created_at", "fecha_ambigua"),
        ("clinica_a:4419", "phone", "telefono_no_verificado"),
        ("clinica_a:4426", "country", "pais_desconocido"),
        ("clinica_a:4422", "phone", "dato_ausente"),
    ],
)
def test_REQ_NOR_001_los_avisos_van_al_informe_con_el_lead_y_el_campo(
    informe, lead_id, campo, codigo
):
    avisos = [(aviso["lead_id"], aviso["campo"], aviso["codigo"]) for aviso in informe["avisos"]]

    assert (lead_id, campo, codigo) in avisos


def test_REQ_NOR_001_los_avisos_no_llevan_valores(informe):
    claves = {"lead_id", "indice", "campo", "codigo"}

    assert all(set(aviso) == claves for aviso in informe["avisos"])
