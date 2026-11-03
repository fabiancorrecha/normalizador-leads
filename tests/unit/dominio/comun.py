"""Datos de prueba compartidos por los tests del dominio: sintéticos, de los exports de docs/."""

from datetime import datetime
from zoneinfo import ZoneInfo

MADRID = ZoneInfo("Europe/Madrid")
MESES_ES = {
    "ene": 1,
    "feb": 2,
    "mar": 3,
    "abr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "ago": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dic": 12,
}
EXPORT_DE_A = datetime(2026, 10, 27, 8, 14, tzinfo=MADRID)
