"""El flag de calidad y el histórico acumulado de punta a punta por la CLI (REQ-NOR-028 a 030)."""

import json

from .conftest import DOCS, RAIZ, ejecutar_cli, leer_json, leer_jsonl

EXPORTS = {
    "clinica_a": DOCS / "clinica_a_leads.json",
    "clinica_b": DOCS / "clinica_b_leads.json",
    "clinica_c": RAIZ / "tests" / "datos" / "clinica_c_leads.json",
}


def normalizar(clinica, salida, historico):
    argumentos = (
        "--clinica", clinica, "--entrada", str(EXPORTS[clinica]),
        "--salida", str(salida), "--historico", str(historico),
    )  # fmt: skip
    resultado = ejecutar_cli(*argumentos)
    assert resultado.returncode == 0, resultado.stderr
    return leer_json(salida / "informe.json")


def test_REQ_NOR_028_el_informe_lleva_la_calidad_por_campo_de_la_clinica_a(tmp_path):
    informe = normalizar("clinica_a", tmp_path / "a", tmp_path / "historico.jsonl")

    calidad = informe["calidad"]
    assert calidad["por_campo"]["created_at"] == {
        "con_aviso": 2,
        "porcentaje": 20.0,
        "motivos": {"fecha_ambigua": 1, "fecha_fuera_de_rango": 1},
    }
    assert calidad["por_campo"]["country"]["motivos"] == {"pais_desconocido": 2}
    assert calidad["por_campo"]["full_name"] == {"con_aviso": 0, "porcentaje": 0.0, "motivos": {}}


def test_REQ_NOR_028_el_informe_lleva_los_campos_no_mapeados_y_los_posibles_duplicados(tmp_path):
    informe = normalizar("clinica_a", tmp_path / "a", tmp_path / "historico.jsonl")

    assert informe["calidad"]["campos_no_mapeados"] == ["estado", "origen"]
    assert informe["calidad"]["posibles_duplicados"] == [
        {"campo": "email", "lead_ids": ["clinica_a:4417", "clinica_a:4420"]},
        {"campo": "phone", "lead_ids": ["clinica_a:4417", "clinica_a:4420"]},
    ]
    assert informe["leads_normalizados"] == 10  # no se fusiona nada


def test_REQ_NOR_029_cada_carga_deja_una_entrada_con_agregados_y_la_siguiente_se_compara(tmp_path):
    historico = tmp_path / "historico.jsonl"

    primero = normalizar("clinica_a", tmp_path / "a", historico)
    segundo = normalizar("clinica_b", tmp_path / "b", historico)

    assert primero["historico"]["cargas_anteriores_de_la_clinica"] == 0
    assert primero["historico"]["cargas_anteriores_en_total"] == 0
    assert primero["historico"]["anotada"] is True
    assert segundo["historico"]["cargas_anteriores_de_la_clinica"] == 0
    assert segundo["historico"]["cargas_anteriores_en_total"] == 1
    created_at = segundo["historico"]["por_campo"]["created_at"]
    assert created_at["acumulado_de_la_clinica"] is None
    assert created_at["acumulado_de_todas"] == 20.0  # la clínica A tuvo 2 de 10
    entradas = leer_jsonl(historico)
    assert [(e["perfil"], e["leads"]) for e in entradas] == [("clinica_a", 10), ("clinica_b", 5)]
    assert set(entradas[0]) == {
        "perfil",
        "huella",
        "fecha",
        "registros",
        "leads",
        "cuarentena",
        "por_campo",
    }
    assert entradas[0]["por_campo"]["created_at"]["con_aviso"] == 2


def test_REQ_NOR_029_una_segunda_carga_de_la_misma_clinica_se_compara_con_su_acumulado(
    tmp_path,
):
    historico = tmp_path / "historico.jsonl"
    normalizar("clinica_a", tmp_path / "a1", historico)
    entradas = leer_jsonl(historico)
    # Otra carga de A (otra huella) con 0 avisos en created_at, escrita a mano solo con agregados.
    entradas.append({**entradas[0], "huella": "otra", "por_campo": {}})
    historico.write_text("".join(json.dumps(e) + "\n" for e in entradas), encoding="utf-8")

    informe = normalizar("clinica_a", tmp_path / "a2", historico)

    assert informe["historico"]["cargas_anteriores_de_la_clinica"] == 2
    created_at = informe["historico"]["por_campo"]["created_at"]
    assert created_at["porcentaje"] == 20.0
    assert created_at["acumulado_de_la_clinica"] == 10.0  # (2 + 0) de (10 + 10)
    assert created_at["diferencia_con_la_clinica"] == 10.0


def test_REQ_NOR_029_el_historico_no_lleva_ningun_valor_de_los_leads(tmp_path):
    historico = tmp_path / "historico.jsonl"
    for clinica in EXPORTS:
        normalizar(clinica, tmp_path / clinica, historico)

    texto = historico.read_text(encoding="utf-8")
    for export in EXPORTS.values():
        registros = json.loads(export.read_text(encoding="utf-8"))
        for valor in _valores_personales(registros):
            assert valor not in texto, valor


def test_REQ_NOR_030_el_mismo_export_con_el_mismo_perfil_no_duplica_su_entrada(tmp_path):
    historico = tmp_path / "historico.jsonl"

    primero = normalizar("clinica_a", tmp_path / "a1", historico)
    segundo = normalizar("clinica_a", tmp_path / "a2", historico)

    assert primero["historico"]["anotada"] is True
    assert segundo["historico"]["anotada"] is False
    assert segundo["historico"]["cargas_anteriores_de_la_clinica"] == 1
    assert len(leer_jsonl(historico)) == 1
    assert primero["huella"] == segundo["huella"]


def test_REQ_NOR_030_la_huella_cambia_si_cambia_el_export(tmp_path, config_de_prueba):
    historico = tmp_path / "historico.jsonl"
    primero = normalizar("clinica_a", tmp_path / "a1", historico)
    export = json.loads(EXPORTS["clinica_a"].read_text(encoding="utf-8"))
    export["registros"] = export["registros"][:5]
    recortado = tmp_path / "clinica_a_recortado.json"
    recortado.write_text(json.dumps(export, ensure_ascii=False), encoding="utf-8")

    resultado = ejecutar_cli(
        "--clinica", "clinica_a", "--entrada", str(recortado),
        "--salida", str(tmp_path / "a2"), "--historico", str(historico),
    )  # fmt: skip

    assert resultado.returncode == 0, resultado.stderr
    segundo = leer_json(tmp_path / "a2" / "informe.json")
    assert segundo["huella"] != primero["huella"]
    assert len(leer_jsonl(historico)) == 2


def test_REQ_NOR_029_sin_historico_en_disco_la_primera_carga_lo_crea(tmp_path):
    historico = tmp_path / "carpeta_nueva" / "historico.jsonl"

    informe = normalizar("clinica_c", tmp_path / "c", historico)

    assert historico.exists()
    assert informe["historico"]["anotada"] is True


def _valores_personales(objeto):
    """Nombres, emails, teléfonos y mensajes de un export, a cualquier profundidad."""
    claves = {
        "nombre_completo", "email", "tel", "mensaje", "first_name", "last_name", "mail", "mobile",
        "enquiry", "correo_electronico", "telefono_movil", "consulta", "nombre", "apellidos",
    }  # fmt: skip
    if isinstance(objeto, dict):
        for clave, valor in objeto.items():
            if clave in claves and isinstance(valor, str) and len(valor.strip()) >= 4:
                yield valor.strip()
            yield from _valores_personales(valor)
    elif isinstance(objeto, list):
        for elemento in objeto:
            yield from _valores_personales(elemento)
