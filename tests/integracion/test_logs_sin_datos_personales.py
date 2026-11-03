"""Los logs llevan lead_id, perfil y datos técnicos; nunca datos del paciente (REQ-NOR-027)."""

import json
import logging

from normalizador.cli import main

from .conftest import DOCS, PERFIL_COMO_A, escribir_export

PACIENTE = {
    "id": 77,
    "nombre_completo": "Zoraida Prueba Única",
    "contacto": {"email": "zoraida.unica@example.com", "tel": "+34 699 111 222"},
    "pais": "España",
    "mensaje": "Me duele la rodilla desde hace semanas y tengo una resonancia.",
    "fecha_alta": "20/10/2026",
}
DATOS_PERSONALES = ["Zoraida", "Única", "zoraida.unica", "699", "rodilla", "resonancia", "España"]


def texto_de_los_logs(caplog) -> str:
    lineas = []
    for registro in caplog.records:
        datos = json.dumps(getattr(registro, "datos", {}), ensure_ascii=False)
        lineas.append(f"{registro.getMessage()} {datos}")
    return "\n".join(lineas)


def normalizar(config, clinica, entrada, salida) -> int:
    argumentos = ["--clinica", clinica, "--entrada", str(entrada), "--salida", str(salida)]
    if config is not None:
        argumentos = ["--config", str(config), *argumentos]
    return main(argumentos)


def test_REQ_NOR_027_los_logs_de_una_carga_no_llevan_datos_del_paciente(
    tmp_path, config_de_prueba, caplog
):
    config = config_de_prueba("prueba", PERFIL_COMO_A.format(source="prueba"))
    registros = [PACIENTE, {**PACIENTE, "id": None}, "basura"]
    entrada = escribir_export(tmp_path / "export.json", registros)
    caplog.set_level(logging.INFO, logger="normalizador")

    codigo = normalizar(config, "prueba", entrada, tmp_path / "salida")

    assert codigo == 0
    logs = texto_de_los_logs(caplog)
    assert caplog.records, "la carga tiene que dejar logs"
    for dato in DATOS_PERSONALES:
        assert dato not in logs
    assert "prueba:77" in logs  # el lead_id sí
    assert "sin_identificador" in logs and "registro_no_valido" in logs  # los motivos sí


def test_REQ_NOR_027_los_logs_del_export_de_a_no_llevan_nada_de_los_pacientes(tmp_path, caplog):
    export = json.loads((DOCS / "clinica_a_leads.json").read_text(encoding="utf-8"))
    caplog.set_level(logging.INFO, logger="normalizador")

    codigo = normalizar(None, "clinica_a", DOCS / "clinica_a_leads.json", tmp_path / "salida")

    assert codigo == 0
    logs = texto_de_los_logs(caplog)
    for registro in export["registros"]:
        contacto = registro["contacto"]
        if not isinstance(contacto, dict):
            contacto = {"tel": contacto}
        valores = (
            registro["nombre_completo"].strip(),
            contacto.get("email"),
            contacto.get("tel"),
            registro["mensaje"],
        )
        for valor in valores:
            assert not valor or valor not in logs


def test_REQ_NOR_027_un_error_de_carga_se_registra_sin_datos_del_export(
    tmp_path, config_de_prueba, caplog
):
    config = config_de_prueba("prueba", PERFIL_COMO_A.format(source="prueba"))
    entrada = escribir_export(tmp_path / "export.json", [PACIENTE], exportado=None)
    caplog.set_level(logging.INFO, logger="normalizador")

    codigo = normalizar(config, "prueba", entrada, tmp_path / "salida")

    assert codigo == 1
    logs = texto_de_los_logs(caplog)
    assert "exportado" in logs
    for dato in DATOS_PERSONALES:
        assert dato not in logs
