"""Una clínica nueva entra solo con configuración (REQ-NOR-017): A, B y C dan su mapeo de referencia
(REQ-NOR-016) por la CLI, con los mismos archivos de src/."""

import json
from itertools import combinations

import pytest

from .conftest import DOCS, RAIZ, ejecutar_cli, leer_json, leer_jsonl

EXPORTS = {
    "clinica_a": DOCS / "clinica_a_leads.json",
    "clinica_b": DOCS / "clinica_b_leads.json",
    "clinica_c": RAIZ / "tests" / "datos" / "clinica_c_leads.json",
}
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
    "clinica_c": {
        "lead_id": "codigo",
        "full_name": "paciente.nombre+paciente.apellidos",
        "email": "correo_electronico",
        "phone": "telefono_movil",
        "country": "nacionalidad",
        "created_at": "fecha_registro",
        "enquiry_text": "consulta",
    },
}
REGISTROS = {"clinica_a": 10, "clinica_b": 5, "clinica_c": 6}
EN_CUARENTENA = {"clinica_a": 0, "clinica_b": 0, "clinica_c": 1}


@pytest.fixture(scope="module")
def salidas(tmp_path_factory):
    salidas = {}
    for clinica, export in EXPORTS.items():
        salida = tmp_path_factory.mktemp("salida") / clinica
        argumentos = ("--clinica", clinica, "--entrada", str(export), "--salida", str(salida))
        resultado = ejecutar_cli(*argumentos)
        assert resultado.returncode == 0, f"{clinica}: {resultado.stderr}"
        salidas[clinica] = salida
    return salidas


def leads_de(salidas, clinica):
    return {lead["lead_id"]: lead for lead in leer_jsonl(salidas[clinica] / "leads.jsonl")}


@pytest.mark.parametrize("clinica", list(EXPORTS))
def test_REQ_NOR_016_REQ_NOR_017_cada_clinica_da_su_mapeo_de_referencia(salidas, clinica):
    informe = leer_json(salidas[clinica] / "informe.json")

    mapeo = {campo: datos["ruta"] for campo, datos in informe["mapeo"].items()}
    assert mapeo == MAPEO_DE_REFERENCIA[clinica]
    assert all(datos["origen"] == "reranking" for datos in informe["mapeo"].values())
    assert all(datos["aviso"] is None for datos in informe["mapeo"].values())


@pytest.mark.parametrize("clinica", list(EXPORTS))
def test_REQ_NOR_017_ningun_registro_se_pierde_en_ninguna_clinica(salidas, clinica):
    informe = leer_json(salidas[clinica] / "informe.json")

    assert informe["registros_de_entrada"] == REGISTROS[clinica]
    assert informe["leads_normalizados"] == REGISTROS[clinica] - EN_CUARENTENA[clinica]
    assert informe["en_cuarentena"] == EN_CUARENTENA[clinica]


def test_REQ_NOR_017_la_clinica_b_sale_normalizada(salidas):
    leads = leads_de(salidas, "clinica_b")

    assert leads["clinica_b:CV-2026-0881"] == {
        "lead_id": "clinica_b:CV-2026-0881",
        "source": "clinica_b",
        "full_name": "Linnea Johansson",
        "email": "linnea.johansson@example.se",
        "phone": "+46702219043",
        "country": "SE",
        "created_at": "2026-10-22T07:41:00Z",
        "enquiry_text": leads["clinica_b:CV-2026-0881"]["enquiry_text"],
        "specialty": "traumatología",  # extraídos del texto por diccionario (T-001-6)
        "urgency": "media",
        "has_reports": True,
        "language": "en",
    }
    assert leads["clinica_b:CV-2026-0881"]["enquiry_text"].startswith("Hi, I am looking into hip")
    assert leads["clinica_b:CV-2026-0884"]["email"] is None
    assert leads["clinica_b:CV-2026-0883"]["created_at"] == "2026-10-25T23:03:00Z"
    assert [lead["country"] for lead in leads.values()] == ["SE", "IT", "BD", "PL", "NG"]


def test_REQ_NOR_017_la_clinica_c_sale_normalizada_con_su_cuarentena(salidas):
    leads = leads_de(salidas, "clinica_c")
    informe = leer_json(salidas["clinica_c"] / "informe.json")

    assert leads["clinica_c:L-0001"] == {
        "lead_id": "clinica_c:L-0001",
        "source": "clinica_c",
        "full_name": "Ingrid Berg",
        "email": "ingrid.berg@example.no",
        "phone": "+4791234567",  # sin prefijo: con el país del lead
        "country": "NO",
        "created_at": "2026-10-27T23:00:00Z",  # 10/28/2026 (mm/dd) en Europe/Oslo, ya en UTC+1
        "enquiry_text": leads["clinica_c:L-0001"]["enquiry_text"],
        "specialty": "traumatología",  # extraídos del texto por diccionario (T-001-6)
        "urgency": "baja",
        "has_reports": True,
        "language": "no",
    }
    assert informe["referencia"] == "2026-11-02T08:30:00Z"  # `export.fecha`, en mm/dd/aaaa hh:mm
    assert leads["clinica_c:L-0006"]["full_name"] == "Emma"  # apellidos vacíos
    assert leads["clinica_c:L-0004"]["created_at"] == "2026-03-03T23:00:00Z"  # 03/04: 4 de marzo
    assert leer_jsonl(salidas["clinica_c"] / "cuarentena.jsonl") == [
        {"indice": 4, "lead_id": None, "motivo": "sin_identificador"}
    ]
    avisos = {(aviso["lead_id"], aviso["campo"], aviso["codigo"]) for aviso in informe["avisos"]}
    assert ("clinica_c:L-0004", "created_at", "fecha_fuera_de_rango") in avisos
    assert ("clinica_c:L-0006", "phone", "telefono_no_verificado") in avisos


def test_REQ_NOR_017_las_tres_clinicas_no_comparten_ni_un_nombre_de_campo():
    claves = {
        clinica: claves_de(json.loads(export.read_text(encoding="utf-8")))
        for clinica, export in EXPORTS.items()
    }

    for una, otra in combinations(claves, 2):
        assert claves[una].isdisjoint(claves[otra]), (una, otra, claves[una] & claves[otra])


def claves_de(objeto) -> set[str]:
    """Todas las claves de un export, a cualquier profundidad."""
    if isinstance(objeto, dict):
        return set(objeto) | {clave for valor in objeto.values() for clave in claves_de(valor)}
    if isinstance(objeto, list):
        return {clave for elemento in objeto for clave in claves_de(elemento)}
    return set()
