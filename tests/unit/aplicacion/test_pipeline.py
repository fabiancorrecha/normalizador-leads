"""El pipeline con puertos falsos: destinos, informe y referencia (REQ-NOR-002 y 003)."""

import dataclasses
import pathlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from normalizador.adaptadores.configuracion import cargar_diccionario
from normalizador.aplicacion.pipeline import Pipeline, RegistroEnCuarentena, ResultadoDeCarga
from normalizador.aplicacion.puertos import ExportIlegible
from normalizador.dominio.extraccion import SIN_TEXTO
from normalizador.dominio.fechas import LecturaDeFechas
from normalizador.dominio.mapeo import LecturaDelExportado, PerfilDeClinica

RAIZ = pathlib.Path(__file__).resolve().parents[3]
DICCIONARIO = cargar_diccionario(RAIZ / "config" / "diccionario.yaml")
MADRID = ZoneInfo("Europe/Madrid")
PERFIL = PerfilDeClinica(
    source="prueba",
    ruta_registros="registros",
    lectura=LecturaDeFechas(("%d/%m/%Y",), MADRID, DICCIONARIO.meses),
    antiguedad_maxima_dias=180,
    exportado=LecturaDelExportado("exportado", LecturaDeFechas(("%d/%m/%Y %H:%M",), MADRID)),
)
PERFIL_SIN_EXPORTADO = PerfilDeClinica(
    source="prueba", ruta_registros="", lectura=PERFIL.lectura, antiguedad_maxima_dias=180
)
REGISTRO = {
    "id": 1,
    "nombre_completo": "Ana Prueba",
    "contacto": {"email": "ANA@example.com", "tel": "+34 612 345 678"},
    "pais": "España",
    "mensaje": "Quiero una consulta de traumatología para la rodilla.",
    "fecha_alta": "20/10/2026",
}
EXPORTADO = "27/10/2026 08:14"
ENTRADA = pathlib.Path("export.json")
SALIDA = pathlib.Path("salida")


class LectorFalso:
    def __init__(self, export):
        self.export = export

    def leer(self, ruta):
        return self.export


@dataclass
class EscritorFalso:
    escrito: list[tuple[pathlib.Path, ResultadoDeCarga]] = field(default_factory=list)

    def escribir(self, carpeta, resultado):
        self.escrito.append((carpeta, resultado))


class RelojFijo:
    def ahora(self):
        return datetime(2026, 10, 27, 10, 0, tzinfo=UTC)


class ExtractorNulo:
    """Un extractor que no extrae nada: el pipeline se prueba sin diccionario ni modelo."""

    def extraer(self, texto):
        return SIN_TEXTO


def pipeline(export, perfil=PERFIL, escritor=None, extraccion=None):
    return Pipeline(
        DICCIONARIO,
        perfil,
        LectorFalso(export),
        escritor or EscritorFalso(),
        ExtractorNulo(),
        RelojFijo(),
        None,
        extraccion,
    )


def test_REQ_NOR_002_cada_registro_acaba_en_leads_o_en_cuarentena():
    registros = [REGISTRO, "basura", {**REGISTRO, "id": " "}]
    export = {"exportado": EXPORTADO, "registros": registros}

    resultado = pipeline(export).ejecutar(ENTRADA, SALIDA)

    assert resultado.registros_de_entrada == 3
    assert [lead.lead_id for lead in resultado.leads] == ["prueba:1"]
    assert [(r.indice, r.motivo) for r in resultado.cuarentena] == [
        (1, "registro_no_valido"),
        (2, "sin_identificador"),
    ]
    assert resultado.registros_de_entrada == len(resultado.leads) + len(resultado.cuarentena)


def test_REQ_NOR_003_un_identificador_repetido_va_a_cuarentena_con_su_lead_id():
    repetido = {**REGISTRO, "id": "1", "contacto": {"email": "otra@example.com"}}
    export = {"exportado": EXPORTADO, "registros": [REGISTRO, repetido]}

    resultado = pipeline(export).ejecutar(ENTRADA, SALIDA)

    assert [lead.lead_id for lead in resultado.leads] == ["prueba:1"]
    assert resultado.cuarentena == (RegistroEnCuarentena(1, "prueba:1", "identificador_repetido"),)
    assert resultado.informe()["cuarentena_por_motivo"] == {"identificador_repetido": 1}


def test_REQ_NOR_018_un_mapeo_explicito_a_una_ruta_que_el_export_no_trae_para_la_carga():
    perfil = dataclasses.replace(PERFIL, mapeo_explicito={"email": "contacto.correo"})
    escritor = EscritorFalso()
    export = {"exportado": EXPORTADO, "registros": [REGISTRO]}

    with pytest.raises(ExportIlegible) as error:
        pipeline(export, perfil=perfil, escritor=escritor).ejecutar(ENTRADA, SALIDA)

    assert "email" in str(error.value) and "contacto.correo" in str(error.value)
    assert escritor.escrito == []


def test_el_informe_dice_con_que_extractor_salio_la_carga():
    descripcion = {"extractor": "diccionario", "modelo": None, "prompt": None}
    export = {"exportado": EXPORTADO, "registros": [REGISTRO]}

    informe = pipeline(export, extraccion=descripcion).ejecutar(ENTRADA, SALIDA).informe()

    assert informe["extraccion"] == descripcion


def test_REQ_NOR_002_el_informe_cuadra_y_lleva_el_mapeo_y_los_avisos():
    registros = [REGISTRO, {**REGISTRO, "id": 2, "pais": None}]
    export = {"exportado": EXPORTADO, "registros": registros}

    informe = pipeline(export).ejecutar(ENTRADA, SALIDA).informe()

    assert informe["perfil"] == "prueba"
    assert informe["entrada"] == "export.json"
    assert informe["referencia"] == "2026-10-27T07:14:00Z"
    assert informe["registros_de_entrada"] == 2
    assert informe["leads_normalizados"] == 2
    assert informe["en_cuarentena"] == 0
    assert informe["mapeo"]["email"]["ruta"] == "contacto.email"
    aviso = {"lead_id": "prueba:2", "indice": 1, "campo": "country", "codigo": "pais_desconocido"}
    assert aviso in informe["avisos"]
    assert informe["cuarentena_por_motivo"] == {}


def test_REQ_NOR_001_el_lead_sale_normalizado_y_la_extraccion_nula_deja_urgencia_media():
    export = {"exportado": EXPORTADO, "registros": [REGISTRO]}

    lead = pipeline(export).ejecutar(ENTRADA, SALIDA).leads[0]

    assert (lead.source, lead.full_name, lead.email) == ("prueba", "Ana Prueba", "ana@example.com")
    assert (lead.phone, lead.country) == ("+34612345678", "ES")
    assert lead.created_at == "2026-10-19T22:00:00Z"
    assert lead.enquiry_text == REGISTRO["mensaje"]
    extraccion = (lead.specialty, lead.urgency, lead.has_reports, lead.language)
    assert extraccion == (None, "media", None, None)


def test_REQ_NOR_002_el_escritor_recibe_el_resultado_y_la_carpeta_de_salida():
    escritor = EscritorFalso()
    export = {"exportado": EXPORTADO, "registros": []}

    resultado = pipeline(export, escritor=escritor).ejecutar(ENTRADA, SALIDA)

    assert escritor.escrito == [(SALIDA, resultado)]
    assert resultado.registros_de_entrada == 0


def test_REQ_NOR_002_sin_exportado_en_el_perfil_la_referencia_es_el_reloj_inyectado():
    resultado = pipeline([REGISTRO], perfil=PERFIL_SIN_EXPORTADO).ejecutar(ENTRADA, SALIDA)

    assert resultado.referencia == datetime(2026, 10, 27, 10, 0, tzinfo=UTC)
    assert resultado.leads[0].created_at == "2026-10-19T22:00:00Z"


@pytest.mark.parametrize(
    ("export", "motivo"),
    [
        ([REGISTRO], "registros"),  # el perfil espera `registros` y llega una lista
        ({"exportado": EXPORTADO}, "registros"),
        ({"exportado": EXPORTADO, "registros": {"no": "lista"}}, "registros"),
        ({"registros": [REGISTRO]}, "exportado"),  # declarado en el perfil, ausente en el export
        ({"exportado": "ayer", "registros": [REGISTRO]}, "exportado"),
        ({"exportado": "27/10/2026", "registros": [REGISTRO]}, "exportado"),  # sin hora
    ],
)
def test_REQ_NOR_002_un_export_que_no_cumple_el_perfil_para_la_carga_sin_escribir(export, motivo):
    escritor = EscritorFalso()

    with pytest.raises(ExportIlegible) as error:
        pipeline(export, escritor=escritor).ejecutar(ENTRADA, SALIDA)

    assert error.value.archivo == str(ENTRADA)
    assert motivo in str(error.value)
    assert escritor.escrito == []
