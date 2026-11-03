"""Carga y validación del diccionario y de los perfiles de clínica (REQ-NOR-018)."""

import pathlib
from zoneinfo import ZoneInfo

import pytest
import yaml

from normalizador.adaptadores.configuracion import (
    ConfiguracionNoValida,
    cargar_diccionario,
    cargar_perfil,
)
from normalizador.dominio.diccionario import Diccionario
from normalizador.dominio.mapeo import PerfilDeClinica

RAIZ = pathlib.Path(__file__).resolve().parents[3]
DICCIONARIO_REAL = RAIZ / "config" / "diccionario.yaml"
DICCIONARIO_MINIMO = {
    "version": 1,
    "mapeo": {"peso_nombre": 0.5, "peso_contenido": 0.5, "umbral": 0.6, "margen": 0.15},
    "campos": {
        "lead_id": {"sinonimos": ["id"], "validador": "identificador"},
        "email": {"sinonimos": ["email", "mail"], "validador": "email"},
    },
    "paises": {"España": "ES", "Spain": "ES"},
    "meses": {"ene": 1, "oct": 10},
}
PERFIL_MINIMO = {
    "source": "clinica_x",
    "registros": "registros",
    "zona_horaria": "Europe/Madrid",
    "fechas": {"formatos": ["%d/%m/%Y", "epoch_s"], "antiguedad_maxima_dias": 180},
    "exportado": {"ruta": "exportado", "formatos": ["%d/%m/%Y %H:%M"]},
    "mapeo": {"email": "contacto.correo"},
}


def escribir(tmp_path, nombre, contenido):
    ruta = tmp_path / nombre
    if not isinstance(contenido, str):
        contenido = yaml.safe_dump(contenido, allow_unicode=True)
    ruta.write_text(contenido, encoding="utf-8")
    return ruta


def con(base, **cambios):
    return {**base, **cambios}


def con_mapeo(**cambios):
    return con(DICCIONARIO_MINIMO, mapeo={**DICCIONARIO_MINIMO["mapeo"], **cambios})


def test_REQ_NOR_018_el_diccionario_del_proyecto_es_valido():
    diccionario = cargar_diccionario(DICCIONARIO_REAL)

    assert isinstance(diccionario, Diccionario)
    assert {campo.nombre for campo in diccionario.campos} == {
        "lead_id",
        "full_name",
        "email",
        "phone",
        "country",
        "created_at",
        "enquiry_text",
    }
    assert diccionario.paises.codigo_de("Líbano") == "LB"
    assert diccionario.paises.codigo_de("Bangladesh") == "BD"
    assert diccionario.meses["oct"] == 10


def test_REQ_NOR_018_un_perfil_valido_da_las_reglas_de_la_clinica(tmp_path):
    diccionario = cargar_diccionario(escribir(tmp_path, "diccionario.yaml", DICCIONARIO_MINIMO))

    perfil = cargar_perfil(escribir(tmp_path, "clinica_x.yaml", PERFIL_MINIMO), diccionario)

    assert isinstance(perfil, PerfilDeClinica)
    assert perfil.source == "clinica_x"
    assert perfil.ruta_registros == "registros"
    assert perfil.lectura.zona == ZoneInfo("Europe/Madrid")
    assert perfil.lectura.formatos == ("%d/%m/%Y", "epoch_s")
    assert perfil.lectura.meses == {"ene": 1, "oct": 10}  # los meses salen del diccionario
    assert perfil.antiguedad_maxima_dias == 180
    assert perfil.exportado.ruta == "exportado"
    assert perfil.exportado.lectura.formatos == ("%d/%m/%Y %H:%M",)
    assert perfil.mapeo_explicito == {"email": "contacto.correo"}


def test_REQ_NOR_018_un_perfil_sin_exportado_ni_mapeo_usa_los_valores_por_defecto(tmp_path):
    diccionario = cargar_diccionario(escribir(tmp_path, "diccionario.yaml", DICCIONARIO_MINIMO))
    minimo = {"source": "clinica_y", "zona_horaria": "UTC", "fechas": {"formatos": ["iso8601"]}}

    perfil = cargar_perfil(escribir(tmp_path, "clinica_y.yaml", minimo), diccionario)

    assert perfil.ruta_registros == ""
    assert perfil.exportado is None
    assert perfil.mapeo_explicito == {}
    assert perfil.antiguedad_maxima_dias == 180


@pytest.mark.parametrize(
    ("contenido", "campo"),
    [
        (con_mapeo(umbral=2), "mapeo.umbral"),
        (con_mapeo(peso_nombre=1.5), "mapeo.peso_nombre"),
        (con_mapeo(peso_nombre=0.7), "mapeo"),  # los pesos tienen que sumar 1
        (
            con(
                DICCIONARIO_MINIMO,
                campos={"codigo_postal": {"sinonimos": ["cp"], "validador": "texto"}},
            ),
            "campos.codigo_postal",
        ),
        (
            con(
                DICCIONARIO_MINIMO,
                campos={"email": {"sinonimos": ["mail"], "validador": "correo"}},
            ),
            "campos.email.validador",
        ),
        (con(DICCIONARIO_MINIMO, paises={"Reino Unido": "UK"}), "paises"),
        (con(DICCIONARIO_MINIMO, meses={"oct": 13}), "meses"),
        ({k: v for k, v in DICCIONARIO_MINIMO.items() if k != "campos"}, "campos"),
        ("- no soy un diccionario\n", ""),
        ("campos: [", ""),
    ],
)
def test_REQ_NOR_018_un_diccionario_no_valido_falla_con_archivo_y_campo(tmp_path, contenido, campo):
    ruta = escribir(tmp_path, "diccionario.yaml", contenido)

    with pytest.raises(ConfiguracionNoValida) as error:
        cargar_diccionario(ruta)

    assert error.value.archivo == str(ruta)
    assert error.value.campo.startswith(campo)
    assert str(ruta) in str(error.value)


@pytest.mark.parametrize(
    ("contenido", "campo"),
    [
        (con(PERFIL_MINIMO, zona_horaria="Europe/Madriz"), "zona_horaria"),
        (con(PERFIL_MINIMO, fechas={"formatos": ["%d/%Q/%Y"]}), "fechas.formatos"),
        (con(PERFIL_MINIMO, fechas={"formatos": []}), "fechas.formatos"),
        (
            con(PERFIL_MINIMO, fechas={"formatos": ["%d-%b-%Y"], "antiguedad_maxima_dias": 0}),
            "fechas",
        ),
        (con(PERFIL_MINIMO, exportado={"ruta": "exportado", "formatos": ["%d/%m"]}), "exportado"),
        (con(PERFIL_MINIMO, mapeo={"codigo_postal": "cp"}), "mapeo.codigo_postal"),
        (con(PERFIL_MINIMO, source="Clínica A"), "source"),  # el source es un identificador
        ({k: v for k, v in PERFIL_MINIMO.items() if k != "source"}, "source"),
        (con(PERFIL_MINIMO, inventado=1), "inventado"),
    ],
)
def test_REQ_NOR_018_un_perfil_no_valido_falla_con_archivo_y_campo(tmp_path, contenido, campo):
    diccionario = cargar_diccionario(escribir(tmp_path, "diccionario.yaml", DICCIONARIO_MINIMO))
    ruta = escribir(tmp_path, "clinica_x.yaml", contenido)

    with pytest.raises(ConfiguracionNoValida) as error:
        cargar_perfil(ruta, diccionario)

    assert error.value.archivo == str(ruta)
    assert error.value.campo.startswith(campo)


def test_REQ_NOR_018_un_archivo_que_no_existe_falla_con_su_ruta(tmp_path):
    ruta = tmp_path / "no_existe.yaml"

    with pytest.raises(ConfiguracionNoValida) as error:
        cargar_diccionario(ruta)

    assert error.value.archivo == str(ruta)
