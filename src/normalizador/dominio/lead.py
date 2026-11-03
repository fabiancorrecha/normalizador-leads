"""El esquema común de salida: un lead normalizado con los 12 campos de SPEC-001."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

type Urgencia = Literal["alta", "media", "baja"]


@dataclass(frozen=True)
class Lead:
    lead_id: str
    source: str
    full_name: str | None
    email: str | None
    phone: str | None
    country: str | None
    created_at: str | None
    enquiry_text: str | None
    specialty: str | None
    urgency: Urgencia
    has_reports: bool | None
    language: str | None
