"""Los 15 registros de los exports de ejemplo de docs/, campo a campo (detalle de T-001-2).

El mapeo de cada clínica lo hará la configuración (T-001-3); aquí va escrito a mano para probar solo
los normalizadores. Perfil de prueba de A: dd/mm/aaaa, aaaa-mm-dd, dd-mes-aaaa y epoch en
Europe/Madrid; B trae ISO 8601 con desfase. Rango: 180 días hasta el export de A (27/10/2026 08:14).
"""

import json
import pathlib

import pytest

from normalizador.dominio.avisos import Aviso
from normalizador.dominio.contacto import normalizar_email, normalizar_telefono
from normalizador.dominio.fechas import LecturaDeFechas, RangoPlausible, normalizar_fecha
from normalizador.dominio.identidad import (
    AliasDePaises,
    construir_lead_id,
    copiar_texto_original,
    normalizar_nombre,
    normalizar_pais,
)

from .comun import EXPORT_DE_A, MADRID, MESES_ES

DOCS = pathlib.Path(__file__).resolve().parents[3] / "docs"
LECTURAS = {
    "clinica_a": LecturaDeFechas(("%d/%m/%Y", "%Y-%m-%d", "%d-%b-%Y", "epoch_s"), MADRID, MESES_ES),
    "clinica_b": LecturaDeFechas(("iso8601",), MADRID),
}
RANGO = RangoPlausible(referencia=EXPORT_DE_A, dias_maximos=180)
ALIAS = AliasDePaises.desde(
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


def _registros_de_a():
    export = json.loads((DOCS / "clinica_a_leads.json").read_text(encoding="utf-8"))
    registros = {}
    for registro in export["registros"]:
        contacto = registro["contacto"]
        contacto = contacto if isinstance(contacto, dict) else {"tel": contacto}  # el 4421
        registros[("clinica_a", str(registro["id"]))] = {
            "id": registro["id"],
            "nombre": (registro["nombre_completo"],),
            "email": contacto.get("email"),
            "telefono": contacto.get("tel"),
            "pais": registro.get("pais"),
            "fecha": registro["fecha_alta"],
            "texto": registro["mensaje"],
        }
    return registros


def _registros_de_b():
    export = json.loads((DOCS / "clinica_b_leads.json").read_text(encoding="utf-8"))
    return {
        ("clinica_b", registro["ref"]): {
            "id": registro["ref"],
            "nombre": (registro["first_name"], registro["last_name"]),
            "email": registro["mail"],
            "telefono": registro["mobile"],
            "pais": registro["residence"],
            "fecha": registro["received_at"],
            "texto": registro["enquiry"],
        }
        for registro in export
    }


REGISTROS = {**_registros_de_a(), **_registros_de_b()}
CLAVES = sorted(REGISTROS)

# Valor esperado y, si lo hay, el código de su aviso.
FECHAS = {
    ("clinica_a", "4417"): ("2026-10-26T23:00:00Z", None),
    ("clinica_a", "4418"): ("2026-10-20T22:00:00Z", None),
    ("clinica_a", "4419"): ("2026-10-20T22:00:00Z", None),
    ("clinica_a", "4420"): ("2026-10-26T23:00:00Z", None),
    ("clinica_a", "4421"): ("2025-10-27T00:00:00Z", "fecha_fuera_de_rango"),
    ("clinica_a", "4422"): ("2026-10-18T22:00:00Z", None),
    ("clinica_a", "4423"): ("2026-04-02T22:00:00Z", "fecha_fuera_de_rango"),  # 03/04, dd/mm
    ("clinica_a", "4424"): ("2026-10-24T22:00:00Z", None),
    ("clinica_a", "4425"): ("2026-10-22T22:00:00Z", None),
    ("clinica_a", "4426"): ("2026-10-23T22:00:00Z", None),
    ("clinica_b", "CV-2026-0881"): ("2026-10-22T07:41:00Z", None),
    ("clinica_b", "CV-2026-0882"): ("2026-10-20T14:12:00Z", None),
    ("clinica_b", "CV-2026-0883"): ("2026-10-25T23:03:00Z", None),
    ("clinica_b", "CV-2026-0884"): ("2026-10-18T09:30:00Z", None),
    ("clinica_b", "CV-2026-0885"): ("2026-10-25T13:55:00Z", None),
}
TELEFONOS = {
    ("clinica_a", "4417"): ("+9613442118", None),
    ("clinica_a", "4418"): ("+79125550142", None),
    ("clinica_a", "4419"): ("+447700900182", "telefono_no_verificado"),
    ("clinica_a", "4420"): ("+9613442118", None),
    ("clinica_a", "4421"): ("+212661304822", None),
    ("clinica_a", "4422"): (None, "dato_ausente"),
    ("clinica_a", "4423"): (None, "dato_ausente"),
    ("clinica_a", "4424"): ("+79031182277", None),
    ("clinica_a", "4425"): ("+971508824410", None),
    ("clinica_a", "4426"): ("+525544128890", None),
    ("clinica_b", "CV-2026-0881"): ("+46702219043", None),
    ("clinica_b", "CV-2026-0882"): ("+393357724418", None),
    ("clinica_b", "CV-2026-0883"): ("+8801711556677", None),
    ("clinica_b", "CV-2026-0884"): ("+48601448920", None),
    ("clinica_b", "CV-2026-0885"): ("+2348032217788", None),
}
EMAILS = {
    ("clinica_a", "4417"): ("mariam.khoury@example.com", None),
    ("clinica_a", "4418"): ("d.volkov@example.ru", None),
    ("clinica_a", "4419"): ("john.reeves@example.co.uk", None),
    ("clinica_a", "4420"): ("mariam.khoury@example.com", None),
    ("clinica_a", "4421"): (None, "dato_ausente"),
    ("clinica_a", "4422"): ("a.schmitt@example.de", None),
    ("clinica_a", "4423"): ("paulo.mendes@example.pt", None),
    ("clinica_a", "4424"): ("elena.petrova@example.ru", None),
    ("clinica_a", "4425"): ("y.haddad@example.ae", None),
    ("clinica_a", "4426"): ("sofia.narvaez@example.mx", None),
    ("clinica_b", "CV-2026-0881"): ("linnea.johansson@example.se", None),
    ("clinica_b", "CV-2026-0882"): ("m.ferrari@example.it", None),
    ("clinica_b", "CV-2026-0883"): ("aisha.rahman@example.com", None),
    ("clinica_b", "CV-2026-0884"): (None, "dato_ausente"),
    ("clinica_b", "CV-2026-0885"): ("grace.okafor@example.ng", None),
}
PAISES = {
    ("clinica_a", "4417"): ("LB", None),
    ("clinica_a", "4418"): ("RU", None),
    ("clinica_a", "4419"): ("GB", None),
    ("clinica_a", "4420"): ("LB", None),
    ("clinica_a", "4421"): ("MA", None),
    ("clinica_a", "4422"): (None, "pais_desconocido"),
    ("clinica_a", "4423"): ("PT", None),
    ("clinica_a", "4424"): ("RU", None),
    ("clinica_a", "4425"): ("AE", None),
    ("clinica_a", "4426"): (None, "pais_desconocido"),
    ("clinica_b", "CV-2026-0881"): ("SE", None),
    ("clinica_b", "CV-2026-0882"): ("IT", None),
    ("clinica_b", "CV-2026-0883"): ("BD", None),
    ("clinica_b", "CV-2026-0884"): ("PL", None),
    ("clinica_b", "CV-2026-0885"): ("NG", None),
}
NOMBRES = {
    ("clinica_a", "4417"): "Mariam Khoury",
    ("clinica_a", "4418"): "Dmitri Volkov",
    ("clinica_a", "4419"): "John Reeves",
    ("clinica_a", "4420"): "Mariam Khoury",
    ("clinica_a", "4421"): "Fatima Benali",
    ("clinica_a", "4422"): "Andreas Schmitt",
    ("clinica_a", "4423"): "Paulo Mendes",
    ("clinica_a", "4424"): "Elena Petrova",
    ("clinica_a", "4425"): "Youssef Haddad",
    ("clinica_a", "4426"): "Sofía Narváez",
    ("clinica_b", "CV-2026-0881"): "Linnea Johansson",
    ("clinica_b", "CV-2026-0882"): "Marco Ferrari",
    ("clinica_b", "CV-2026-0883"): "Aisha Rahman",
    ("clinica_b", "CV-2026-0884"): "Tomasz Nowak",
    ("clinica_b", "CV-2026-0885"): "Grace Okafor",
}


def esperado(campo, valor_y_codigo):
    valor, codigo = valor_y_codigo
    return valor, ((Aviso(campo, codigo),) if codigo else ())


def obtenido(normalizado):
    return normalizado.valor, normalizado.avisos


@pytest.mark.parametrize("clave", CLAVES)
def test_REQ_NOR_005_REQ_NOR_006_fecha_de_cada_registro_de_ejemplo(clave):
    fecha = normalizar_fecha(REGISTROS[clave]["fecha"], LECTURAS[clave[0]], RANGO)

    assert obtenido(fecha) == esperado("created_at", FECHAS[clave])


@pytest.mark.parametrize("clave", CLAVES)
def test_REQ_NOR_007_telefono_de_cada_registro_de_ejemplo(clave):
    pais = normalizar_pais(REGISTROS[clave]["pais"], ALIAS).valor
    telefono = normalizar_telefono(REGISTROS[clave]["telefono"], pais)

    assert obtenido(telefono) == esperado("phone", TELEFONOS[clave])


@pytest.mark.parametrize("clave", CLAVES)
def test_REQ_NOR_008_email_de_cada_registro_de_ejemplo(clave):
    assert obtenido(normalizar_email(REGISTROS[clave]["email"])) == esperado("email", EMAILS[clave])


@pytest.mark.parametrize("clave", CLAVES)
def test_REQ_NOR_009_nombre_de_cada_registro_de_ejemplo(clave):
    assert obtenido(normalizar_nombre(*REGISTROS[clave]["nombre"])) == (NOMBRES[clave], ())


@pytest.mark.parametrize("clave", CLAVES)
def test_REQ_NOR_010_pais_de_cada_registro_de_ejemplo(clave):
    pais = normalizar_pais(REGISTROS[clave]["pais"], ALIAS)

    assert obtenido(pais) == esperado("country", PAISES[clave])


@pytest.mark.parametrize("clave", CLAVES)
def test_REQ_NOR_011_lead_id_de_cada_registro_de_ejemplo(clave):
    source, id_original = clave

    assert obtenido(construir_lead_id(source, REGISTROS[clave]["id"])) == (
        f"{source}:{id_original}",
        (),
    )


@pytest.mark.parametrize("clave", CLAVES)
def test_REQ_NOR_012_texto_de_cada_registro_de_ejemplo(clave):
    texto = REGISTROS[clave]["texto"]

    assert obtenido(copiar_texto_original(texto)) == (texto, ())
