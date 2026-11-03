"""Contacto del paciente: teléfono en E.164 y email normalizado (REQ-NOR-007 y 008)."""

from __future__ import annotations

import re
import unicodedata

import phonenumbers

from normalizador.dominio.avisos import Normalizado, esta_ausente

CAMPO_TELEFONO = "phone"
CAMPO_EMAIL = "email"
TELEFONO_NO_VALIDO = "telefono_no_valido"
TELEFONO_SIN_REGION = "telefono_sin_region"
TELEFONO_NO_VERIFICADO = "telefono_no_verificado"
EMAIL_NO_VALIDO = "email_no_valido"

FORMATO_DE_EMAIL = re.compile(r"[^@\s:]+@[^@\s.:]+(?:\.[^@\s.:]+)+")
CARACTERES_INVISIBLES = frozenset({"Cc", "Cf"})  # de control y de formato, como el de ancho cero


def normalizar_telefono(valor: object, pais: str | None) -> Normalizado[str]:
    """E.164. Un número sin prefijo internacional se interpreta con el país del propio lead.

    `pais` es un código ISO 3166-1 alfa-2 en mayúsculas, como lo deja `normalizar_pais`; uno que
    phonenumbers no conoce cuenta como sin país. Un número posible (longitud y prefijo) que no está
    asignado se conserva con `telefono_no_verificado`: puede ser de otro país, leído con el de
    residencia. La spec da por bueno `07700 900182`, de un rango británico reservado para ficción.
    """
    if esta_ausente(valor):
        return Normalizado.ausente(CAMPO_TELEFONO)
    if not isinstance(valor, str):
        return Normalizado.con_aviso(CAMPO_TELEFONO, TELEFONO_NO_VALIDO)
    texto = valor.strip()
    region = pais if pais in phonenumbers.SUPPORTED_REGIONS else None
    if region is None and not texto.startswith("+"):
        return Normalizado.con_aviso(CAMPO_TELEFONO, TELEFONO_SIN_REGION)
    try:
        numero = phonenumbers.parse(texto, region)
    except phonenumbers.NumberParseException:
        return Normalizado.con_aviso(CAMPO_TELEFONO, TELEFONO_NO_VALIDO)
    if not phonenumbers.is_possible_number(numero):
        return Normalizado.con_aviso(CAMPO_TELEFONO, TELEFONO_NO_VALIDO)
    e164 = phonenumbers.format_number(numero, phonenumbers.PhoneNumberFormat.E164)
    if not phonenumbers.is_valid_number(numero):
        return Normalizado.con_aviso(CAMPO_TELEFONO, TELEFONO_NO_VERIFICADO, e164)
    return Normalizado(e164)


def normalizar_email(valor: object) -> Normalizado[str]:
    if esta_ausente(valor):
        return Normalizado.ausente(CAMPO_EMAIL)
    if not isinstance(valor, str):
        return Normalizado.con_aviso(CAMPO_EMAIL, EMAIL_NO_VALIDO)
    email = valor.strip().lower()
    if not FORMATO_DE_EMAIL.fullmatch(email) or _tiene_invisibles(email):
        return Normalizado.con_aviso(CAMPO_EMAIL, EMAIL_NO_VALIDO)
    return Normalizado(email)


def _tiene_invisibles(texto: str) -> bool:
    return any(unicodedata.category(letra) in CARACTERES_INVISIBLES for letra in texto)
