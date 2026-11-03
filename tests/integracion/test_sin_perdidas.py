"""Ningún registro se pierde: normalizado o en cuarentena con motivo (REQ-NOR-002 y 003).

También: un export ilegible, o que no cumple el perfil, para la carga sin escribir nada.
"""

import json

import pytest

from .conftest import DOCS, PERFIL_COMO_A, ejecutar_cli, escribir_export, leer_json, leer_jsonl

REGISTRO_VALIDO = {
    "id": 1,
    "nombre_completo": "Ana Prueba",
    "contacto": {"email": "ana@example.com", "tel": "+34 612 345 678"},
    "pais": "España",
    "mensaje": "Quiero una consulta de traumatología para la rodilla.",
    "fecha_alta": "20/10/2026",
}
SIN_IDENTIFICADOR = {**REGISTRO_VALIDO, "id": None}
EXPORT_DE_A = DOCS / "clinica_a_leads.json"


def normalizar(config, nombre, entrada, salida):
    argumentos = ["--clinica", nombre, "--entrada", str(entrada), "--salida", str(salida)]
    if config is not None:
        argumentos = ["--config", str(config), *argumentos]
    return ejecutar_cli(*argumentos)


def test_REQ_NOR_002_entrada_igual_a_normalizados_mas_cuarentena_con_el_export_de_a(tmp_path):
    salida = tmp_path / "salida"

    resultado = normalizar(None, "clinica_a", EXPORT_DE_A, salida)

    assert resultado.returncode == 0, resultado.stderr
    informe = leer_json(salida / "informe.json")
    leads = leer_jsonl(salida / "leads.jsonl")
    cuarentena = leer_jsonl(salida / "cuarentena.jsonl")
    assert informe["registros_de_entrada"] == len(leads) + len(cuarentena) == 10
    assert informe["leads_normalizados"] == len(leads)
    assert informe["en_cuarentena"] == len(cuarentena)


def test_REQ_NOR_003_los_registros_no_validos_van_a_cuarentena_y_el_resto_sigue(
    tmp_path, config_de_prueba
):
    config = config_de_prueba("prueba", PERFIL_COMO_A.format(source="prueba"))
    registros = [
        REGISTRO_VALIDO,
        "basura",
        SIN_IDENTIFICADOR,
        42,
        None,
        {**REGISTRO_VALIDO, "id": 2},
    ]
    entrada = escribir_export(tmp_path / "export.json", registros)
    salida = tmp_path / "salida"

    resultado = normalizar(config, "prueba", entrada, salida)

    assert resultado.returncode == 0, resultado.stderr
    leads = leer_jsonl(salida / "leads.jsonl")
    cuarentena = leer_jsonl(salida / "cuarentena.jsonl")
    assert [lead["lead_id"] for lead in leads] == ["prueba:1", "prueba:2"]
    assert cuarentena == [
        {"indice": 1, "lead_id": None, "motivo": "registro_no_valido"},
        {"indice": 2, "lead_id": None, "motivo": "sin_identificador"},
        {"indice": 3, "lead_id": None, "motivo": "registro_no_valido"},
        {"indice": 4, "lead_id": None, "motivo": "registro_no_valido"},
    ]
    informe = leer_json(salida / "informe.json")
    assert informe["registros_de_entrada"] == 6 == len(leads) + len(cuarentena)
    assert informe["cuarentena_por_motivo"] == {"registro_no_valido": 3, "sin_identificador": 1}


def test_REQ_NOR_002_la_cuarentena_no_lleva_datos_del_registro(tmp_path, config_de_prueba):
    config = config_de_prueba("prueba", PERFIL_COMO_A.format(source="prueba"))
    entrada = escribir_export(tmp_path / "export.json", [SIN_IDENTIFICADOR])
    salida = tmp_path / "salida"

    normalizar(config, "prueba", entrada, salida)

    texto = (salida / "cuarentena.jsonl").read_text(encoding="utf-8")
    assert "Ana" not in texto
    assert "ana@example.com" not in texto
    assert "612" not in texto


@pytest.mark.parametrize(
    ("contenido", "motivo"),
    [
        (None, "no se puede leer"),  # el archivo no existe
        ("{ esto no es JSON", "no es JSON"),
        (json.dumps([REGISTRO_VALIDO]), "registros"),  # el perfil espera `registros`
        (json.dumps({"registros": "no es una lista"}), "registros"),
        (json.dumps({"registros": [REGISTRO_VALIDO]}), "exportado"),  # falta la fecha del export
        (json.dumps({"registros": [REGISTRO_VALIDO], "exportado": "ayer"}), "exportado"),
    ],
)
def test_REQ_NOR_002_un_export_ilegible_para_la_carga_sin_escribir_nada(
    tmp_path, config_de_prueba, contenido, motivo
):
    config = config_de_prueba("prueba", PERFIL_COMO_A.format(source="prueba"))
    entrada = tmp_path / "export.json"
    if contenido is not None:
        entrada.write_text(contenido, encoding="utf-8")
    salida = tmp_path / "salida"

    resultado = normalizar(config, "prueba", entrada, salida)

    assert resultado.returncode == 1
    assert "export.json" in resultado.stderr
    assert motivo in resultado.stderr
    assert "Traceback" not in resultado.stderr
    assert not salida.exists()


def test_REQ_NOR_018_un_perfil_que_no_existe_para_la_carga_sin_escribir_nada(
    tmp_path, config_de_prueba
):
    config = config_de_prueba("prueba", PERFIL_COMO_A.format(source="prueba"))
    entrada = escribir_export(tmp_path / "export.json", [REGISTRO_VALIDO])
    salida = tmp_path / "salida"

    resultado = normalizar(config, "otra", entrada, salida)

    assert resultado.returncode == 1
    assert "otra.yaml" in resultado.stderr
    assert not salida.exists()


def test_REQ_NOR_018_un_perfil_no_valido_para_la_carga_con_archivo_y_campo(
    tmp_path, config_de_prueba
):
    perfil = PERFIL_COMO_A.format(source="prueba").replace("Europe/Madrid", "Europe/Madriz")
    config = config_de_prueba("prueba", perfil)
    entrada = escribir_export(tmp_path / "export.json", [REGISTRO_VALIDO])
    salida = tmp_path / "salida"

    resultado = normalizar(config, "prueba", entrada, salida)

    assert resultado.returncode == 1
    assert "prueba.yaml" in resultado.stderr
    assert "zona_horaria" in resultado.stderr
    assert not salida.exists()


def test_REQ_NOR_001_un_nombre_de_clinica_que_no_es_un_identificador_se_rechaza(tmp_path):
    resultado = normalizar(None, "../clinica_a", EXPORT_DE_A, tmp_path)

    assert resultado.returncode == 2
    assert "--clinica" in resultado.stderr
