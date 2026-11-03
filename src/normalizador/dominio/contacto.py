"""Contacto del paciente: teléfono en E.164 y email normalizado (REQ-NOR-007 y 008)."""

from __future__ import annotations

import re

import phonenumbers
from phonenumbers import NumberParseException, ValidationResult

from normalizador.dominio.avisos import Normalizado, esta_ausente, tiene_invisibles

CAMPO_TELEFONO = "phone"
CAMPO_EMAIL = "email"
TELEFONO_NO_VALIDO = "telefono_no_valido"
TELEFONO_SIN_REGION = "telefono_sin_region"
TELEFONO_NO_VERIFICADO = "telefono_no_verificado"
EMAIL_NO_VALIDO = "email_no_valido"

# Parte local sin signos de agrupación ni puntos seguidos; dominio con etiquetas de letras y
# dígitos (guiones solo dentro) y un sufijo de al menos dos letras.
FORMATO_DE_EMAIL = re.compile(
    r'[^\s@()<>\[\]:;,\\".]+(?:\.[^\s@()<>\[\]:;,\\".]+)*'  # parte local
    r"@(?:[^\W_]+(?:-+[^\W_]+)*\.)+[^\W\d_]{2,}"  # dominio
)
PREFIJO_INTERNACIONAL = re.compile(r"\D*[+＋]")


def normalizar_telefono(valor: object, pais: str | None) -> Normalizado[str]:
    """E.164. Un número sin prefijo internacional se interpreta con el país del propio lead.

    `pais` es un código ISO 3166-1 alfa-2 en mayúsculas, como lo deja `normalizar_pais`; uno que
    phonenumbers no conoce cuenta como sin país. Un número completo que no está asignado se
    conserva con `telefono_no_verificado`: puede ser de otro país, leído con el de residencia. La
    spec da por bueno `07700 900182`, de un rango británico reservado para ficción.
    """
    if esta_ausente(valor):
        return Normalizado.ausente(CAMPO_TELEFONO)
    if not isinstance(valor, str):
        return Normalizado.con_aviso(CAMPO_TELEFONO, TELEFONO_NO_VALIDO)
    texto = valor.strip()
    region = pais if pais in phonenumbers.SUPPORTED_REGIONS else None
    try:
        numero = phonenumbers.parse(texto, region)
    except NumberParseException as error:
        if _le_falta_la_region(error, region, texto):
            return Normalizado.con_aviso(CAMPO_TELEFONO, TELEFONO_SIN_REGION)
        return Normalizado.con_aviso(CAMPO_TELEFONO, TELEFONO_NO_VALIDO)
    if phonenumbers.is_possible_number_with_reason(numero) != ValidationResult.IS_POSSIBLE:
        return Normalizado.con_aviso(CAMPO_TELEFONO, TELEFONO_NO_VALIDO)
    e164 = phonenumbers.format_number(numero, phonenumbers.PhoneNumberFormat.E164)
    if not phonenumbers.is_valid_number(numero):
        return Normalizado.con_aviso(CAMPO_TELEFONO, TELEFONO_NO_VERIFICADO, e164)
    return Normalizado(e164)


def _le_falta_la_region(error: NumberParseException, region: str | None, texto: str) -> bool:
    """Un número nacional sin país: phonenumbers no sabe de qué país es y no trae prefijo."""
    return (
        error.error_type == NumberParseException.INVALID_COUNTRY_CODE
        and region is None
        and PREFIJO_INTERNACIONAL.match(texto) is None
    )


def normalizar_email(valor: object) -> Normalizado[str]:
    if esta_ausente(valor):
        return Normalizado.ausente(CAMPO_EMAIL)
    if not isinstance(valor, str):
        return Normalizado.con_aviso(CAMPO_EMAIL, EMAIL_NO_VALIDO)
    email = valor.strip().lower()
    if tiene_invisibles(email) or not FORMATO_DE_EMAIL.fullmatch(email):
        return Normalizado.con_aviso(CAMPO_EMAIL, EMAIL_NO_VALIDO)
    return Normalizado(email)
