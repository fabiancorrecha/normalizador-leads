"""El esquema común de salida: los 12 campos de la spec, en su orden."""

from dataclasses import fields

from normalizador.dominio.lead import Lead

CAMPOS_DE_LA_SPEC = (
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
)


def test_REQ_NOR_001_el_lead_tiene_exactamente_los_12_campos_del_esquema():
    assert tuple(campo.name for campo in fields(Lead)) == CAMPOS_DE_LA_SPEC
