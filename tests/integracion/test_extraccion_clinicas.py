"""La extracción del texto libre de punta a punta por la CLI, con A, B y C (REQ-NOR-019 a 023)."""

import pytest

from .conftest import DOCS, RAIZ, ejecutar_cli, leer_jsonl

EXPORTS = {
    "clinica_a": DOCS / "clinica_a_leads.json",
    "clinica_b": DOCS / "clinica_b_leads.json",
    "clinica_c": RAIZ / "tests" / "datos" / "clinica_c_leads.json",
}


@pytest.fixture(scope="module")
def leads(tmp_path_factory):
    leads = {}
    for clinica, export in EXPORTS.items():
        salida = tmp_path_factory.mktemp("salida") / clinica
        argumentos = ("--clinica", clinica, "--entrada", str(export), "--salida", str(salida))
        resultado = ejecutar_cli(*argumentos)
        assert resultado.returncode == 0, f"{clinica}: {resultado.stderr}"
        leads.update({lead["lead_id"]: lead for lead in leer_jsonl(salida / "leads.jsonl")})
    return leads


@pytest.mark.parametrize(
    ("lead_id", "specialty", "urgency", "has_reports", "language"),
    [
        ("clinica_a:4417", "traumatología", "alta", True, "es"),
        ("clinica_a:4421", "oncología", "alta", True, "fr"),
        ("clinica_a:4424", "cirugía plástica", "media", None, "ru"),
        ("clinica_a:4426", "cardiología", "baja", False, "es"),
        ("clinica_b:CV-2026-0882", "cirugía bariátrica", "baja", False, "it"),
        ("clinica_b:CV-2026-0883", "oncología", "alta", True, "en"),
        ("clinica_c:L-0001", "traumatología", "baja", True, "no"),
        ("clinica_c:L-0003", "cardiología", "alta", True, "sv"),
    ],
)
def test_REQ_NOR_019_REQ_NOR_020_REQ_NOR_021_REQ_NOR_022_los_leads_salen_con_su_extraccion(
    leads, lead_id, specialty, urgency, has_reports, language
):
    lead = leads[lead_id]

    assert (lead["specialty"], lead["urgency"]) == (specialty, urgency)
    assert (lead["has_reports"], lead["language"]) == (has_reports, language)


@pytest.mark.parametrize("lead_id", ["clinica_a:4423", "clinica_c:L-0006"])
def test_REQ_NOR_023_un_lead_sin_texto_sale_con_nulos_y_urgencia_media(leads, lead_id):
    lead = leads[lead_id]

    assert lead["enquiry_text"] == ""
    assert (lead["specialty"], lead["urgency"]) == (None, "media")
    assert (lead["has_reports"], lead["language"]) == (None, None)


def test_REQ_NOR_019_todas_las_especialidades_salen_del_catalogo(leads):
    catalogo = {
        "traumatología",
        "cardiología",
        "oncología",
        "reproducción asistida",
        "oftalmología",
        "cirugía bariátrica",
        "cirugía plástica",
        None,
    }

    assert {lead["specialty"] for lead in leads.values()} <= catalogo
    assert {lead["urgency"] for lead in leads.values()} <= {"alta", "media", "baja"}
