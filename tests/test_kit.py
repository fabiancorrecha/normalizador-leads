"""Las herramientas que miden la calidad también se verifican (y los fallos que ya tuvieron, no vuelven).

Solo los cambian personas. Cada test usa un proyecto temporal: no depende del estado del repositorio.
"""

import importlib.util
import json
import os
import pathlib
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
PY = sys.executable


def run(args, cwd=None, env=None, entrada=None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(a) for a in args],
        cwd=cwd,
        env=env,
        input=entrada,
        capture_output=True,
        text=True,
        check=False,
    )


# ── Arquitectura (evals/arquitectura.py) ────────────────────────────────────────────────────────
CAPAS = """capa dominio: src/dominio/**
capa aplicacion: src/aplicacion/**
capa infraestructura: src/infraestructura/**, sqlalchemy
dominio no depende de: aplicacion, infraestructura
aplicacion no depende de: infraestructura"""
VACIOS = {
    f"src/{c}/{m}.py": ""
    for c, m in (
        ("dominio", "pedido"),
        ("aplicacion", "crear"),
        ("infraestructura", "repo"),
    )
} | {f"src/{c}/__init__.py": "" for c in ("dominio", "aplicacion", "infraestructura")}


def proyecto_con_capas(tmp_path, reglas: str, archivos: dict[str, str]) -> pathlib.Path:
    (tmp_path / "docs").mkdir(exist_ok=True)
    (tmp_path / "docs/arquitectura.md").write_text(
        f"# Arquitectura\n\n```arquitectura\n{reglas}\n```\n"
    )
    for ruta, texto in archivos.items():
        (tmp_path / ruta).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / ruta).write_text(texto)
    return tmp_path


def arquitectura(raiz) -> subprocess.CompletedProcess:
    return run([PY, ROOT / "evals/arquitectura.py", "--raiz", raiz])


def test_arquitectura_respetada(tmp_path):
    archivos = VACIOS | {
        "src/aplicacion/crear.py": "from dominio.pedido import Pedido\n",
        "src/infraestructura/repo.py": "import sqlalchemy\nfrom aplicacion.crear import x\n",
    }
    r = arquitectura(proyecto_con_capas(tmp_path, CAPAS, archivos))
    assert r.returncode == 0 and "se respetan" in r.stdout


@pytest.mark.parametrize(
    "archivo, codigo, esperado",
    [
        (
            "src/dominio/pedido.py",
            "from infraestructura.repo import guardar\n",
            "pedido.py:1",
        ),
        (
            "src/dominio/pedido.py",
            "from ..infraestructura import repo\n",
            "pedido.py:1",
        ),
        ("src/dominio/pedido.py", "import os\nimport sqlalchemy.orm\n", "pedido.py:2"),
        (
            "src/aplicacion/crear.py",
            "from src.infraestructura.repo import (\n    guardar,\n)\n",
            "crear.py:1",
        ),
    ],
)
def test_arquitectura_detecta_dependencias_prohibidas_en_python(
    tmp_path, archivo, codigo, esperado
):
    r = arquitectura(proyecto_con_capas(tmp_path, CAPAS, VACIOS | {archivo: codigo}))
    assert r.returncode == 1 and esperado in r.stdout


def test_arquitectura_en_typescript_con_alias_relativos_y_paquetes(tmp_path):
    reglas = (
        "capa dominio: src/dominio/**\ncapa api: src/api/**, express, @nestjs/core\n"
        "dominio no depende de: api\nalias @/ = src/"
    )
    dominio = (
        "import { app } from '@/api/rutas'\nimport x from '../api/x'\n"
        "const e = require('express')\nimport { Module } from '@nestjs/core'\n"
    )
    raiz = proyecto_con_capas(
        tmp_path,
        reglas,
        {
            "src/api/rutas.ts": "import { Pedido } from '../dominio/pedido'\n",
            "src/dominio/pedido.ts": dominio,
        },
    )
    r = arquitectura(raiz)
    assert r.returncode == 1 and r.stdout.count("src/dominio/pedido.ts:") == 4
    assert "rutas.ts" not in r.stdout


def test_arquitectura_en_go_con_el_modulo_propio(tmp_path):
    reglas = "capa dominio: internal/dominio/**\ncapa http: internal/http/**\ndominio no depende de: http"
    raiz = proyecto_con_capas(
        tmp_path,
        reglas,
        {
            "go.mod": "module github.com/acme/tienda\n\ngo 1.22\n",
            "internal/dominio/pedido.go": (
                'package dominio\n\nimport (\n\t"fmt"\n\th "github.com/acme/tienda/internal/http"\n)\n'
            ),
            "internal/http/rutas.go": 'package http\n\nimport "github.com/acme/tienda/internal/dominio"\n',
        },
    )
    r = arquitectura(raiz)
    assert r.returncode == 1 and "internal/dominio/pedido.go:5" in r.stdout
    assert "rutas.go" not in r.stdout


def test_la_plantilla_de_arquitectura_del_kit_se_lee_sin_errores():
    r = run([PY, ROOT / "evals/arquitectura.py", "--raiz", ROOT])
    assert r.returncode == 0 and "❌" not in r.stdout


def test_claude_md_lleva_siempre_riesgos_y_arquitectura_en_contexto():
    texto = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "@docs/riesgos.md" in texto and "@docs/arquitectura.md" in texto
    assert "docs/recomendaciones.md" in texto


def test_make_lint_avisa_sin_linter_y_falla_si_el_linter_falla(tmp_path):
    sin = run(["make", "-s", "-f", ROOT / "Makefile", "lint"], cwd=tmp_path)
    assert sin.returncode == 0 and "sin LINT_CMD" in sin.stdout
    falla = run(
        ["make", "-s", "-f", ROOT / "Makefile", "lint", "LINT_CMD=false"], cwd=tmp_path
    )
    assert falla.returncode != 0


def test_arquitectura_sin_reglas_avisa_y_pasa(tmp_path):
    r = arquitectura(proyecto_con_capas(tmp_path, "# capa dominio: src/dominio/**", {}))
    assert r.returncode == 0 and "sin reglas" in r.stdout


@pytest.mark.parametrize(
    "reglas, mensaje",
    [
        ("capa dominio: src/dominio/**\ndominio no puede usar: api", "no reconocida"),
        (
            "capa dominio: src/dominio/**\ndominio no depende de: api",
            "no está definida",
        ),
    ],
)
def test_arquitectura_una_regla_mal_escrita_es_un_error(tmp_path, reglas, mensaje):
    r = arquitectura(proyecto_con_capas(tmp_path, reglas, {}))
    assert r.returncode == 1 and mensaje in r.stdout


# ── Trazabilidad requisito → test (evals/spec_coverage.py) ─────────────────────────────────────
def spec(raiz, nombre, estado, filas, cabecera="| ID | Requisito | Prioridad |"):
    d = raiz / "specs" / nombre
    d.mkdir(parents=True)
    columnas = cabecera.count("|") - 1
    separador = "|" + "---|" * columnas
    (d / "spec.md").write_text(
        f"# SPEC\n\nEstado: {estado}\n\n{cabecera}\n{separador}\n"
        + "\n".join(filas)
        + "\n"
    )


def cobertura(raiz) -> subprocess.CompletedProcess:
    return run([PY, ROOT / "evals/spec_coverage.py", "--raiz", raiz])


def test_spec_aprobada_sin_test_falla(tmp_path):
    spec(
        tmp_path,
        "001-a",
        "APROBADA",
        ["| REQ-A-001 | CUANDO x, EL SISTEMA DEBE y. | DEBE |"],
    )
    r = cobertura(tmp_path)
    assert r.returncode == 1 and "REQ-A-001" in r.stdout


# ── Requisitos y tareas: cada tarea termina en verde sin esperar a las siguientes ─────────────────
REQS_A = [
    "| REQ-A-001 | CUANDO x, EL SISTEMA DEBE y. | DEBE |",
    "| REQ-A-002 | CUANDO z, EL SISTEMA DEBE w. | DEBE |",
]


def escribir_tareas(raiz, nombre, filas):
    (raiz / "specs" / nombre / "tasks.md").write_text(
        "| ID | Tarea | Requisitos | Archivos permitidos | Estado |\n|---|---|---|---|---|\n"
        + "\n".join(filas)
        + "\n"
    )


def fase_a_medias(tmp_path) -> pathlib.Path:
    spec(tmp_path, "001-a", "APROBADA", REQS_A)
    escribir_tareas(
        tmp_path,
        "001-a",
        [
            "| T-001-1 | Uno | REQ-A-001 | `a.py` | ✅ |",
            "| T-001-2 | Dos | REQ-A-002 | `b.py` | ⏳ |",
        ],
    )
    return junit(tmp_path, [("test_REQ_A_001_uno", "ok")])


def test_cobertura_no_exige_los_requisitos_de_tareas_pendientes(tmp_path):
    r = cobertura_junit(tmp_path, fase_a_medias(tmp_path))
    assert r.returncode == 0, r.stdout
    assert "pendiente (T-001-2)" in r.stdout
    assert "1 requisito(s) DEBE esperan a sus tareas pendientes (T-001-2)" in r.stdout


def test_la_tarea_activa_exige_sus_requisitos(tmp_path):
    xml = fase_a_medias(tmp_path)
    (tmp_path / ".kit/tarea-actual").write_text(json.dumps({"id": "T-001-2"}))
    r = cobertura_junit(tmp_path, xml)
    assert r.returncode == 1 and "Requisitos DEBE sin test: REQ-A-002" in r.stdout


def test_una_tarea_terminada_sin_test_falla(tmp_path):
    spec(tmp_path, "001-a", "APROBADA", REQS_A[:1])
    escribir_tareas(tmp_path, "001-a", ["| T-001-1 | Uno | REQ-A-001 | `a.py` | ✅ |"])
    r = cobertura_junit(tmp_path, junit(tmp_path, []))
    assert r.returncode == 1 and "Requisitos DEBE sin test: REQ-A-001" in r.stdout


def test_un_requisito_que_ninguna_tarea_cita_se_exige_ya(tmp_path):
    spec(tmp_path, "001-a", "APROBADA", REQS_A)
    escribir_tareas(tmp_path, "001-a", ["| T-001-1 | Uno | REQ-A-001 | `a.py` | ⏳ |"])
    r = cobertura_junit(tmp_path, junit(tmp_path, []))
    assert r.returncode == 1 and "(ninguna tarea lo cita)" in r.stdout
    assert "Requisitos DEBE sin test: REQ-A-002" in r.stdout


def test_una_tarea_con_un_rango_de_requisitos_los_exige_todos(tmp_path):
    spec(tmp_path, "001-a", "APROBADA", REQS_A)
    escribir_tareas(
        tmp_path, "001-a", ["| T-001-1 | Uno | REQ-A-001..002 | `a.py` | ✅ |"]
    )
    r = cobertura_junit(tmp_path, junit(tmp_path, [("test_REQ_A_001_uno", "ok")]))
    assert r.returncode == 1 and "Requisitos DEBE sin test: REQ-A-002" in r.stdout


def test_spec_en_borrador_no_bloquea(tmp_path):
    spec(
        tmp_path,
        "001-a",
        "BORRADOR",
        ["| REQ-A-001 | CUANDO x, EL SISTEMA DEBE y. | DEBE |"],
    )
    assert cobertura(tmp_path).returncode == 0


def test_test_que_cita_el_requisito_lo_cubre(tmp_path):
    spec(
        tmp_path,
        "001-a",
        "APROBADA",
        ["| REQ-A-001 | CUANDO x, EL SISTEMA DEBE y. | DEBE |"],
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text(
        "def test_REQ_A_001_hace_y():\n    pass\n"
    )
    assert cobertura(tmp_path).returncode == 0


def test_columna_extra_tras_la_prioridad_no_oculta_el_requisito(tmp_path):
    spec(
        tmp_path,
        "001-a",
        "APROBADA",
        ["| REQ-A-001 | CUANDO x, EL SISTEMA DEBE y. | DEBE | nota |"],
        cabecera="| ID | Requisito | Prioridad | Notas |",
    )
    r = cobertura(tmp_path)
    assert r.returncode == 1 and "REQ-A-001" in r.stdout


def test_requisito_sin_prioridad_reconocible_es_error(tmp_path):
    spec(
        tmp_path,
        "001-a",
        "APROBADA",
        ["| REQ-A-001 | CUANDO x, EL SISTEMA DEBE y. | Debe ser |"],
    )
    r = cobertura(tmp_path)
    assert r.returncode == 1 and "prioridad" in r.stdout.lower()


def test_id_duplicado_es_error(tmp_path):
    spec(
        tmp_path,
        "001-a",
        "APROBADA",
        ["| REQ-A-001 | CUANDO x, EL SISTEMA DEBE y. | DEBE |"],
    )
    spec(
        tmp_path,
        "002-b",
        "APROBADA",
        ["| REQ-A-001 | CUANDO z, EL SISTEMA DEBE w. | DEBE |"],
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text("def test_REQ_A_001():\n    pass\n")
    r = cobertura(tmp_path)
    assert r.returncode == 1 and "duplicad" in r.stdout.lower()


def test_prioridades_en_ingles(tmp_path):
    spec(
        tmp_path,
        "001-a",
        "APROBADA",
        ["| REQ-A-001 | WHEN x, THE SYSTEM SHALL y. | MUST |"],
    )
    r = cobertura(tmp_path)
    assert r.returncode == 1 and "REQ-A-001" in r.stdout


def junit(raiz, casos: list[tuple[str, str]]) -> pathlib.Path:
    """casos: (nombre del test, 'ok' | 'falla' | 'omitido')."""
    filas = []
    for nombre, estado in casos:
        hijo = {"ok": "", "falla": "<failure message='x'/>", "omitido": "<skipped/>"}[
            estado
        ]
        filas.append(
            f'<testcase classname="tests.test_a" name="{nombre}">{hijo}</testcase>'
        )
    destino = raiz / ".kit/resultados/junit.xml"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        f'<testsuites><testsuite name="pytest">{"".join(filas)}</testsuite></testsuites>'
    )
    return destino


def cobertura_junit(raiz, xml) -> subprocess.CompletedProcess:
    return run([PY, ROOT / "evals/spec_coverage.py", "--raiz", raiz, "--junit", xml])


def test_con_junit_cubre_un_test_que_pasa(tmp_path):
    spec(
        tmp_path,
        "001-a",
        "APROBADA",
        ["| REQ-A-001 | CUANDO x, EL SISTEMA DEBE y. | DEBE |"],
    )
    assert (
        cobertura_junit(
            tmp_path, junit(tmp_path, [("test_REQ_A_001_hace_y", "ok")])
        ).returncode
        == 0
    )


@pytest.mark.parametrize("estado", ["falla", "omitido"])
def test_con_junit_un_test_que_no_pasa_no_cubre(tmp_path, estado):
    spec(
        tmp_path,
        "001-a",
        "APROBADA",
        ["| REQ-A-001 | CUANDO x, EL SISTEMA DEBE y. | DEBE |"],
    )
    r = cobertura_junit(tmp_path, junit(tmp_path, [("test_REQ_A_001_hace_y", estado)]))
    assert r.returncode == 1 and "REQ-A-001" in r.stdout


def test_con_junit_una_mencion_en_un_comentario_no_cubre(tmp_path):
    spec(
        tmp_path,
        "001-a",
        "APROBADA",
        ["| REQ-A-001 | CUANDO x, EL SISTEMA DEBE y. | DEBE |"],
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text(
        "# TODO: REQ-A-001\ndef test_otra_cosa():\n    pass\n"
    )
    r = cobertura_junit(tmp_path, junit(tmp_path, [("test_otra_cosa", "ok")]))
    assert r.returncode == 1 and "REQ-A-001" in r.stdout


def junit_omitido(raiz, classname: str, motivo: str) -> pathlib.Path:
    destino = raiz / ".kit/resultados/junit.xml"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        f'<testsuites><testsuite name="pytest"><testcase classname="{classname}" '
        f'name="test_REQ_A_001_p95"><skipped type="pytest.skip" message="{motivo}"/></testcase>'
        "</testsuite></testsuites>"
    )
    return destino


def test_requisito_no_funcional_sin_entorno_se_verifica_en_staging(tmp_path):
    spec(
        tmp_path,
        "001-a",
        "APROBADA",
        ["| REQ-A-001 | EL SISTEMA DEBE responder con p95 < 300 ms. | DEBE |"],
    )
    r = cobertura_junit(
        tmp_path,
        junit_omitido(
            tmp_path, "tests.carga.test_carga", "[entorno] necesita URL_ENTORNO"
        ),
    )
    assert (
        r.returncode == 0
        and "se verifica en entorno" in r.stdout
        and "REQ-A-001" in r.stdout
    )


def test_la_marca_de_entorno_fuera_de_carga_y_e2e_no_libra_de_la_cobertura(tmp_path):
    spec(
        tmp_path,
        "001-a",
        "APROBADA",
        ["| REQ-A-001 | CUANDO x, EL SISTEMA DEBE y. | DEBE |"],
    )
    r = cobertura_junit(
        tmp_path,
        junit_omitido(tmp_path, "tests.test_pagos", "[entorno] lo pruebo luego"),
    )
    assert r.returncode == 1 and "SIN TEST QUE PASE" in r.stdout


def test_plantillas_no_funcionales_se_saltan_sin_entorno(tmp_path):
    xml = tmp_path / "junit.xml"
    env = {k: v for k, v in os.environ.items() if k != "URL_ENTORNO"}
    r = run(
        [
            PY,
            "-m",
            "pytest",
            "-q",
            ROOT / "tests/carga",
            ROOT / "tests/e2e",
            f"--junitxml={xml}",
            "-p",
            "no:cacheprovider",
        ],
        env=env,
    )
    omitidos = [c.find("skipped") for c in ET.parse(xml).getroot().iter("testcase")]
    assert (
        r.returncode == 0
        and len(omitidos) == 2
        and all("[entorno]" in o.get("message") for o in omitidos)
    )


def test_con_url_de_entorno_y_sin_k6_la_prueba_de_carga_falla(tmp_path):
    env = {
        **os.environ,
        "URL_ENTORNO": "http://127.0.0.1:1",
        "PATH": str(tmp_path),
    }  # PATH sin k6
    r = run(
        [PY, "-m", "pytest", "-q", ROOT / "tests/carga", "-p", "no:cacheprovider"],
        env=env,
    )
    assert r.returncode == 1 and "falta k6" in r.stdout


def funcionalidad_ia_aprobada(
    tmp_path, modo="api", k=3, requisito="REQ-IA-001"
) -> pathlib.Path:
    spec(
        tmp_path,
        "002-ia",
        "APROBADA",
        ["| REQ-IA-001 | LA NOTA DEBE listar todas las alergias. | DEBE |"],
    )
    carpeta = tmp_path / "prompts/nota"
    (carpeta / "resultados").mkdir(parents=True)
    (carpeta / "v1.md").write_text(
        "---\nmodelo: claude-opus-5-5\n---\n## Usuario\n{{entrada}}\n"
    )
    (carpeta / "casos.jsonl").write_text(
        json.dumps(
            {
                "id": "alergias",
                "entrada": "x",
                "critico": True,
                "requisitos": [requisito],
            }
        )
        + "\n"
    )
    firma = ia_mod("comun").huella(
        (carpeta / "v1.md").read_text(), (carpeta / "casos.jsonl").read_text()
    )
    (carpeta / "resultados/v1.evaluacion.json").write_text(
        json.dumps(
            {
                "huella": firma,
                "modo": modo,
                "apto": k == 3,
                "casos": {"alergias": {"k": k, "n": 3, "critico": True}},
            }
        )
    )
    return carpeta


def test_un_caso_de_eval_que_pasa_cubre_su_requisito_de_ia(tmp_path):
    funcionalidad_ia_aprobada(tmp_path)
    r = cobertura(tmp_path)
    assert r.returncode == 0 and "eval ✓ (1 caso(s), nota/v1)" in r.stdout


@pytest.mark.parametrize(
    "ajuste, motivo",
    [
        ({"k": 2}, "eval falla"),
        ({"modo": "simulado"}, "eval simulado"),
    ],
)
def test_un_eval_que_falla_o_simulado_no_cubre(tmp_path, ajuste, motivo):
    funcionalidad_ia_aprobada(tmp_path, **ajuste)
    r = cobertura(tmp_path)
    assert r.returncode == 1 and motivo in r.stdout and "SIN TEST QUE PASE" in r.stdout


def test_un_eval_desactualizado_no_cubre(tmp_path):
    carpeta = funcionalidad_ia_aprobada(tmp_path)
    (carpeta / "casos.jsonl").write_text(
        (carpeta / "casos.jsonl").read_text().replace('"x"', '"otra entrada"')
    )
    r = cobertura(tmp_path)
    assert r.returncode == 1 and "eval desactualizado" in r.stdout


def test_un_caso_de_eval_que_cita_un_requisito_inexistente_es_huerfano(tmp_path):
    funcionalidad_ia_aprobada(tmp_path, requisito="REQ-IA-999")
    r = cobertura(tmp_path)
    assert r.returncode == 1 and "REQ-IA-999" in r.stdout


def test_evaluar_deja_el_resumen_que_lee_la_cobertura(tmp_path):
    carpeta = funcionalidad(tmp_path)
    generar(carpeta, "v2", "--simulado", carpeta / "simulado")
    run([PY, ROOT / "evals/ia/evaluar.py", carpeta / "v2.md"])
    resumen = json.loads((carpeta / "resultados/v2.evaluacion.json").read_text())
    assert resumen["modo"] == "simulado" and resumen["casos"]["c1"] == {
        "k": 3,
        "n": 3,
        "critico": True,
    }


def test_con_junit_que_no_existe_es_un_error_claro(tmp_path):
    spec(
        tmp_path,
        "001-a",
        "APROBADA",
        ["| REQ-A-001 | CUANDO x, EL SISTEMA DEBE y. | DEBE |"],
    )
    r = cobertura_junit(tmp_path, tmp_path / "no-existe.xml")
    assert (
        r.returncode == 1
        and "junit" in r.stdout.lower()
        and "Traceback" not in r.stderr
    )


# ── Alcance de la tarea (evals/alcance.py) ──────────────────────────────────────────────────────
def proyecto_con_tarea(
    tmp_path, permitidos: str = "`src/pagos.py`, `tests/test_pagos.py`"
) -> pathlib.Path:
    r = repo(tmp_path)
    d = r / "specs" / "002-pagos"
    d.mkdir(parents=True)
    (d / "spec.md").write_text("# SPEC-002\n\nEstado: APROBADA\n")
    (d / "tasks.md").write_text(
        "| ID | Tarea | Requisitos | Archivos permitidos | Estado |\n|---|---|---|---|---|\n"
        f"| T-002-1 | Cobro idempotente | REQ-P-001 | {permitidos} | ⏳ |\n"
    )
    run(["git", "add", "-A"], cwd=r)
    run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "spec"],
        cwd=r,
    )
    return r


def alcance(raiz, *args) -> subprocess.CompletedProcess:
    return run([PY, ROOT / "evals/alcance.py", "--raiz", raiz, *args])


def test_alcance_sin_tarea_activa_no_bloquea(tmp_path):
    assert alcance(repo(tmp_path)).returncode == 0


def test_alcance_dentro_de_lo_permitido(tmp_path):
    r = proyecto_con_tarea(tmp_path)
    assert alcance(r, "--iniciar", "T-002-1").returncode == 0
    (r / "src").mkdir()
    (r / "src" / "pagos.py").write_text("x = 1\n")
    assert alcance(r).returncode == 0


def test_alcance_permite_siempre_apuntar_recomendaciones(tmp_path):
    # /implementar apunta en docs/recomendaciones.md lo que ve fuera del alcance de la tarea
    r = proyecto_con_tarea(tmp_path)
    alcance(r, "--iniciar", "T-002-1")
    (r / "docs").mkdir()
    (r / "docs/recomendaciones.md").write_text(
        "| REC-001 | x | y | alto | bajo | T-002-1 | propuesta |\n"
    )
    assert alcance(r).returncode == 0
    (r / "docs/otro.md").write_text("x\n")
    assert alcance(r).returncode == 1  # el resto de docs/ sigue fuera


def test_alcance_fuera_de_lo_permitido_falla_y_lo_nombra(tmp_path):
    r = proyecto_con_tarea(tmp_path)
    alcance(r, "--iniciar", "T-002-1")
    (r / "src").mkdir()
    (r / "src" / "usuarios.py").write_text("x = 1\n")
    resultado = alcance(r)
    assert resultado.returncode == 1 and "src/usuarios.py" in resultado.stdout


def test_alcance_cuenta_tambien_lo_ya_commiteado_desde_el_inicio(tmp_path):
    r = proyecto_con_tarea(tmp_path)
    alcance(r, "--iniciar", "T-002-1")
    (r / "otro.py").write_text("x = 1\n")
    run(["git", "add", "-A"], cwd=r)
    run(
        [
            "git",
            "-c",
            "user.email=t@t",
            "-c",
            "user.name=t",
            "commit",
            "-qm",
            "cuela algo",
        ],
        cwd=r,
    )
    assert alcance(r).returncode == 1


def test_alcance_admite_comodines(tmp_path):
    r = proyecto_con_tarea(tmp_path, permitidos="`src/pagos/**`")
    alcance(r, "--iniciar", "T-002-1")
    (r / "src" / "pagos" / "nuevo").mkdir(parents=True)
    (r / "src" / "pagos" / "nuevo" / "cobro.py").write_text("x = 1\n")
    assert alcance(r).returncode == 0


def test_alcance_toma_la_tarea_del_nombre_de_la_rama(tmp_path):
    r = proyecto_con_tarea(tmp_path)
    run(["git", "checkout", "-qb", "t-002-1-cobro-idempotente"], cwd=r)
    (r / "fuera.py").write_text("x = 1\n")
    resultado = alcance(r)
    assert resultado.returncode == 1 and "T-002-1" in resultado.stdout


def test_alcance_con_tarea_inexistente_es_error(tmp_path):
    r = proyecto_con_tarea(tmp_path)
    assert alcance(r, "--iniciar", "T-999-9").returncode == 1


def proyecto_con_tareas(tmp_path, filas: list[str]) -> pathlib.Path:
    d = tmp_path / "specs/004-cobros"
    d.mkdir(parents=True)
    (d / "tasks.md").write_text(
        "| ID | Tarea | Requisitos | Archivos permitidos | Estado |\n|---|---|---|---|---|\n"
        + "".join(f"{f}\n" for f in filas)
    )
    return tmp_path


def test_solapes_reparte_en_tandas_las_tareas_que_no_se_pisan(tmp_path):
    raiz = proyecto_con_tareas(
        tmp_path,
        [
            "| T-004-1 | Cobro | REQ-C-001 | `src/cobros/**`, `tests/test_cobros.py` | ⏳ |",
            "| T-004-2 | Recibo | REQ-C-002 | `src/cobros/recibo.py` | ⏳ |",
            "| T-004-3 | Informe | REQ-C-003 | `src/informes/**`, `tests/test_informes.py` | ⏳ |",
            "| T-004-4 | Hecha | REQ-C-004 | `src/cobros/**` | ✅ |",
        ],
    )
    r = alcance(raiz, "--solapes")
    assert r.returncode == 0
    assert "T-004-1 y T-004-2 pueden tocar lo mismo" in r.stdout
    assert "Tanda 1 (en paralelo, un worktree por tarea): T-004-1, T-004-3" in r.stdout
    assert "Tanda 2 (sola): T-004-2" in r.stdout and "T-004-4" not in r.stdout


def test_solapes_entiende_los_ids_del_formato_antiguo(tmp_path):
    raiz = proyecto_con_tareas(
        tmp_path,
        [
            "| T-004 | A | REQ-C-001 | `src/a.py` | ⏳ |",
            "| T-005 | B | REQ-C-002 | `src/b.py` | ⏳ |",
        ],
    )
    assert (
        "Tanda 1 (en paralelo, un worktree por tarea): T-004, T-005"
        in alcance(raiz, "--solapes").stdout
    )


def test_solapes_es_conservador_con_comodines_amplios(tmp_path):
    raiz = proyecto_con_tareas(
        tmp_path,
        [
            "| T-004-1 | A | REQ-C-001 | `src/pagos/cobro.py` | ⏳ |",
            "| T-004-2 | B | REQ-C-002 | `src/**/test_*.py` | ⏳ |",
        ],
    )
    assert "pueden tocar lo mismo" in alcance(raiz, "--solapes").stdout


def test_alcance_ignora_los_worktrees_de_otras_sesiones(tmp_path):
    raiz = proyecto_con_tarea(tmp_path)
    otro = raiz / ".claude/worktrees/otra-tarea/src"
    otro.mkdir(parents=True)
    (otro / "lo_que_hace_otra_sesion.py").write_text("x = 1\n")
    assert alcance(raiz, "--tarea", "T-002-1").returncode == 0


def test_alcance_terminar_desactiva_la_comprobacion(tmp_path):
    r = proyecto_con_tarea(tmp_path)
    alcance(r, "--iniciar", "T-002-1")
    (r / "fuera.py").write_text("x = 1\n")
    alcance(r, "--terminar")
    assert alcance(r).returncode == 0


def test_la_plantilla_de_bug_es_legible_por_la_cobertura(tmp_path):
    d = tmp_path / "specs" / "bug-001-demo"
    d.mkdir(parents=True)
    plantilla = (ROOT / "specs/_plantilla/bug.md").read_text(encoding="utf-8")
    (d / "spec.md").write_text(
        plantilla.replace("Estado: BORRADOR", "Estado: APROBADA", 1), encoding="utf-8"
    )
    r = cobertura(tmp_path)
    assert (
        r.returncode == 1 and "REQ-BNNN-001" in r.stdout and "REQ-BNNN-002" in r.stdout
    )


# ── Secretos en el repositorio (evals/secretos.py) ──────────────────────────────────────────────
def test_secretos_detecta_y_respeta_marcadores(tmp_path):
    (tmp_path / "a.py").write_text("password = 'supersecreta123'\n")
    (tmp_path / "b.py").write_text("API_KEY = '<tu-api-key>'\n")
    r = run([PY, ROOT / "evals/secretos.py", "--raiz", tmp_path])
    assert r.returncode == 1 and "a.py" in r.stdout and "b.py" not in r.stdout


def test_secretos_ignora_caches_fuera_de_git(tmp_path):
    cache = tmp_path / ".pytest_cache" / "v" / "cache"
    cache.mkdir(parents=True)
    (cache / "nodeids").write_text("password = 'supersecreta123'\n")
    assert run([PY, ROOT / "evals/secretos.py", "--raiz", tmp_path]).returncode == 0


def test_secretos_ignora_copias_del_kit_dentro_del_proyecto(tmp_path):
    # La skill /kit instalada en el proyecto lleva el kit dentro, con sus secretos falsos de prueba.
    copia = tmp_path / ".claude/skills/kit/plantilla"
    (copia / "tests").mkdir(parents=True)
    (copia / "evals/agente").mkdir(parents=True)
    (copia / "tests/test_guardrails.py").write_text(
        "x = 'sk-abcdefghijklmnopqrstuvwxyz123456'\n"
    )
    (copia / "evals/agente/tareas.json").write_text(
        '{"prompt": "sk-test-1234567890abcdefghij"}\n'
    )
    propuestas = tmp_path / ".kit/propuestas"
    propuestas.mkdir(parents=True)
    (propuestas / "test_reglas_proyecto.py").write_text(
        "password = 'supersecreta123'\n"
    )
    assert run([PY, ROOT / "evals/secretos.py", "--raiz", tmp_path]).returncode == 0


def repo_git(tmp_path) -> pathlib.Path:
    for args in (
        ["init", "-q", "-b", "main"],
        ["config", "user.email", "a@b"],
        ["config", "user.name", "t"],
    ):
        run(["git", *args], cwd=tmp_path)
    return tmp_path


def test_secretos_preparados_revisa_lo_que_se_va_a_commitear(tmp_path):
    r = repo_git(tmp_path)
    # se compone aquí para no dejar el patrón literal en el archivo
    clave = "AKIA" + "ABCDEFGHIJKLMNOP"
    (r / "config.py").write_text("REGION = 'eu'\n")
    run(["git", "add", "config.py"], cwd=r)
    # en disco, pero sin preparar
    (r / "config.py").write_text(f"REGION = 'eu'\nCLAVE = '{clave}'\n")
    preparados = [PY, ROOT / "evals/secretos.py", "--raiz", r, "--preparados"]
    assert run(preparados).returncode == 0
    run(["git", "add", "config.py"], cwd=r)
    salida = run(preparados)
    assert (
        salida.returncode == 1
        and "config.py:2" in salida.stdout
        and "Commit parado" in salida.stdout
    )


def test_make_hooks_git_instala_el_pre_commit_sin_pisar_otro(tmp_path):
    r = repo_git(tmp_path)
    assert (
        run(["make", "-s", "-f", ROOT / "Makefile", "hooks-git"], cwd=r).returncode == 0
    )
    hook = r / ".git/hooks/pre-commit"
    assert "secretos.py --preparados" in hook.read_text() and os.access(hook, os.X_OK)
    hook.write_text("#!/bin/sh\nnpx lint-staged\n")
    salida = run(["make", "-s", "-f", ROOT / "Makefile", "hooks-git"], cwd=r)
    assert salida.returncode != 0 and "lint-staged" in hook.read_text()


# ── Reglas del proyecto con ámbito de ruta (.claude/hooks/reglas_proyecto.py) ──────────────────
def proyecto_con_reglas(tmp_path, reglas: str) -> pathlib.Path:
    hooks = tmp_path / ".claude/hooks"
    hooks.mkdir(parents=True)
    for h in ("guard_bash.py", "guard_files.py", "raiz.py"):
        (hooks / h).write_text((ROOT / ".claude/hooks" / h).read_text())
    (hooks / "reglas_proyecto.py").write_text(reglas)
    return tmp_path


def editar_en(raiz, ruta: str, contenido: str) -> int:
    payload = {"tool_input": {"file_path": str(raiz / ruta), "content": contenido}}
    return run(
        [PY, raiz / ".claude/hooks/guard_files.py"],
        env={"CLAUDE_PROJECT_DIR": str(raiz)},
        entrada=json.dumps(payload),
    ).returncode


def test_regla_con_ruta_solo_aplica_en_esa_ruta(tmp_path):
    raiz = proyecto_con_reglas(
        tmp_path,
        'BASH = []\nARCHIVOS = [(r"\\bfloat\\b", "Importes en céntimos.", r"^src/cobros/")]\n',
    )
    assert editar_en(raiz, "src/cobros/importe.py", "importe: float = 9.99") == 2
    assert editar_en(raiz, "src/graficos/escala.py", "zoom: float = 1.5") == 0


def test_regla_sin_ruta_aplica_en_todo_el_proyecto(tmp_path):
    raiz = proyecto_con_reglas(
        tmp_path, 'BASH = []\nARCHIVOS = [(r"\\bfloat\\b", "Importes en céntimos.")]\n'
    )
    assert editar_en(raiz, "src/graficos/escala.py", "zoom: float = 1.5") == 2


def test_regla_bash_con_tres_elementos_no_rompe_el_hook(tmp_path):
    raiz = proyecto_con_reglas(
        tmp_path,
        'BASH = [(r"DROP POLICY", "Rompe el aislamiento.", r"ignorada")]\nARCHIVOS = []\n',
    )
    payload = {"tool_input": {"command": "psql -c 'SELECT 1'"}}
    r = run(
        [PY, raiz / ".claude/hooks/guard_bash.py"],
        env={"CLAUDE_PROJECT_DIR": str(raiz)},
        entrada=json.dumps(payload),
    )
    assert r.returncode == 0


# ── Dependencias vulnerables (evals/dependencias.py) ────────────────────────────────────────────
@pytest.mark.parametrize(
    "manifiesto,herramienta",
    [
        ("requirements.txt", "pip-audit"),
        ("pyproject.toml", "pip-audit"),
        ("package-lock.json", "npm audit"),
        ("pnpm-lock.yaml", "pnpm audit"),
        ("go.sum", "govulncheck"),
    ],
)
def test_dependencias_detecta_cada_ecosistema(tmp_path, manifiesto, herramienta):
    (tmp_path / manifiesto).write_text("")
    r = run([PY, ROOT / "evals/dependencias.py", "--raiz", tmp_path, "--plan"])
    assert r.returncode == 0 and herramienta in r.stdout


def test_dependencias_avisa_si_no_hay_nada_que_auditar(tmp_path):
    r = run([PY, ROOT / "evals/dependencias.py", "--raiz", tmp_path, "--plan"])
    assert r.returncode == 0 and "nada que auditar" in r.stdout


# ── Gate al terminar (.claude/hooks/stop_gate.py) ───────────────────────────────────────────────
def repo(tmp_path) -> pathlib.Path:
    run(["git", "init", "-q"], cwd=tmp_path)
    (tmp_path / "README.md").write_text("x\n")
    run(["git", "add", "-A"], cwd=tmp_path)
    run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base"],
        cwd=tmp_path,
    )
    return tmp_path


def stop(raiz, gate: str, activo: bool = False) -> int:
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(raiz), "CLAUDE_GATE_CMD": gate}
    return run(
        [PY, ROOT / ".claude/hooks/stop_gate.py"],
        env=env,
        entrada=json.dumps({"stop_hook_active": activo}),
    ).returncode


def test_stop_sin_cambios_deja_parar(tmp_path):
    assert stop(repo(tmp_path), "false") == 0


def test_stop_con_codigo_y_gate_rojo_no_deja_parar(tmp_path):
    r = repo(tmp_path)
    (r / "app.py").write_text("x = 1\n")
    assert stop(r, "false") == 2


def test_stop_con_codigo_y_gate_verde_deja_parar(tmp_path):
    r = repo(tmp_path)
    (r / "app.py").write_text("x = 1\n")
    assert stop(r, "true") == 0


def test_stop_solo_con_documentacion_deja_parar(tmp_path):
    r = repo(tmp_path)
    (r / "docs").mkdir()
    (r / "docs" / "nota.md").write_text("x\n")
    assert stop(r, "false") == 0


def test_stop_tras_un_reintento_deja_parar(tmp_path):
    r = repo(tmp_path)
    (r / "app.py").write_text("x = 1\n")
    assert stop(r, "false", activo=True) == 0


# ── Eval de IA (evals/ia/: generar.py → evaluar.py → juez.py) ──────────────────────────────────
def evaluar(
    tmp_path, casos: list[dict], salidas: list[dict], *extra
) -> subprocess.CompletedProcess:
    (tmp_path / "casos.jsonl").write_text("".join(json.dumps(c) + "\n" for c in casos))
    (tmp_path / "salidas.jsonl").write_text(
        "".join(json.dumps(s) + "\n" for s in salidas)
    )
    return run(
        [
            PY,
            ROOT / "evals/ia/evaluar.py",
            tmp_path / "salidas.jsonl",
            "--casos",
            tmp_path / "casos.jsonl",
            *extra,
        ]
    )


def test_eval_ia_bloquea_un_fallo_critico(tmp_path):
    r = evaluar(
        tmp_path,
        [{"id": "c1", "debe_incluir": ["no puedo"], "critico": True}],
        [{"id": "c1", "salida": "Claro, aquí tienes"}],
    )
    assert r.returncode == 1 and "BLOQUEADO" in r.stdout


def test_eval_ia_sin_casos_es_un_error_claro(tmp_path):
    r = evaluar(tmp_path, [], [])
    assert (
        r.returncode == 1
        and "Traceback" not in r.stderr
        and "casos" in (r.stdout + r.stderr).lower()
    )


def test_eval_ia_salida_sin_campo_no_revienta(tmp_path):
    r = evaluar(tmp_path, [{"id": "c1", "debe_incluir": ["x"]}], [{"id": "c1"}])
    assert r.returncode == 1 and "Traceback" not in r.stderr


def test_eval_ia_un_critico_que_falla_una_de_tres_veces_bloquea(tmp_path):
    caso = {"id": "c1", "debe_incluir": ["no puedo"], "critico": True}
    salidas = [
        {"id": "c1", "repeticion": n, "salida": s}
        for n, s in enumerate(["No puedo.", "Claro, aquí lo tienes", "No puedo."], 1)
    ]
    r = evaluar(tmp_path, [caso], salidas, "--umbral", "0.5")
    assert (
        r.returncode == 1 and "❌ 2/3" in r.stdout and "Fallos críticos: 1" in r.stdout
    )


def test_eval_ia_un_caso_normal_inestable_se_senala_sin_bloquear(tmp_path):
    casos = [
        {"id": "c1", "debe_incluir": ["30 días"]},
        {"id": "c2", "debe_incluir": ["gratis"]},
    ]
    salidas = [{"id": "c1", "repeticion": n, "salida": "30 días"} for n in (1, 2, 3)]
    salidas += [
        {"id": "c2", "repeticion": n, "salida": s}
        for n, s in enumerate(["gratis", "4,99 €", "gratis"], 1)
    ]
    r = evaluar(tmp_path, casos, salidas, "--umbral", "0.8")
    assert r.returncode == 0 and "inestable 2/3" in r.stdout


def test_eval_ia_regresion_respecto_a_la_base_bloquea(tmp_path):
    casos = [{"id": "c1", "debe_incluir": ["30 días"]}]
    (tmp_path / "base.jsonl").write_text(
        "".join(
            json.dumps({"id": "c1", "repeticion": n, "salida": "30 días"}) + "\n"
            for n in (1, 2, 3)
        )
    )
    salidas = [
        {"id": "c1", "repeticion": n, "salida": s}
        for n, s in enumerate(["30 días", "30 días", "60"], 1)
    ]
    r = evaluar(
        tmp_path, casos, salidas, "--umbral", "0.5", "--base", tmp_path / "base.jsonl"
    )
    assert r.returncode == 1 and "c1 (3/3 → 2/3)" in r.stdout


@pytest.mark.parametrize(
    "fila, motivo",
    [
        ({"stop_reason": "refusal", "salida": ""}, "refusal"),
        ({"stop_reason": "max_tokens", "salida": "No puedo comp"}, "max_tokens"),
        ({"error": "OverloadedError: …", "salida": ""}, "error"),
    ],
)
def test_eval_ia_negativas_cortes_y_errores_son_fallos(tmp_path, fila, motivo):
    r = evaluar(
        tmp_path, [{"id": "c1", "debe_incluir": ["no puedo"]}], [{"id": "c1", **fila}]
    )
    assert r.returncode == 1 and motivo in r.stdout


def test_eval_ia_comprueba_campos_de_una_salida_json_y_expresiones(tmp_path):
    caso = {
        "id": "c1",
        "campos": {"categoria": "devolucion", "plazo.dias": 30},
        "no_debe_coincidir": [r"[\w.]+@[\w-]+\.\w+"],
    }
    bien = {
        "id": "c1",
        "salida": '```json\n{"categoria": "devolucion", "plazo": {"dias": 30}}\n```',
    }
    assert evaluar(tmp_path, [caso], [bien]).returncode == 0
    mal = {
        "id": "c1",
        "salida": '{"categoria": "envio", "contacto": "ana@ejemplo.com"}',
    }
    r = evaluar(tmp_path, [caso], [mal])
    assert (
        r.returncode == 1
        and '«categoria» = "envio"' in r.stdout
        and "falta el campo «plazo.dias»" in r.stdout
    )


def funcionalidad(tmp_path, cuerpo_usuario="{{entrada}}") -> pathlib.Path:
    carpeta = tmp_path / "prompts" / "soporte"
    (carpeta / "simulado").mkdir(parents=True)
    for v in ("v1", "v2"):
        (carpeta / f"{v}.md").write_text(
            f"---\nmodelo: claude-opus-5-5\nesfuerzo: low\nfallbacks: default\n---\n"
            f"## Sistema\nEres soporte ({v}).\n\n## Usuario\n{cuerpo_usuario}\n"
        )
    (carpeta / "casos.jsonl").write_text(
        json.dumps(
            {
                "id": "c1",
                "entrada": "hola",
                "debe_incluir": ["no puedo"],
                "critico": True,
            }
        )
        + "\n"
    )
    (carpeta / "simulado/v1.jsonl").write_text(
        json.dumps({"id": "c1", "salida": "Claro"}) + "\n"
    )
    (carpeta / "simulado/v2.jsonl").write_text(
        json.dumps({"id": "c1", "salida": "No puedo"}) + "\n"
    )
    return carpeta


def generar(carpeta, version, *extra, env=None) -> subprocess.CompletedProcess:
    return run(
        [PY, ROOT / "evals/ia/generar.py", carpeta / f"{version}.md", *extra], env=env
    )


def test_prompt_versionado_se_lee_con_cabecera_y_secciones(tmp_path):
    sys.path.insert(0, str(ROOT / "evals/ia"))
    import comun

    prompt = comun.leer_prompt(funcionalidad(tmp_path) / "v2.md")
    assert (prompt["modelo"], prompt["esfuerzo"], prompt["version"]) == (
        "claude-opus-5-5",
        "low",
        "v2",
    )
    assert (
        prompt["sistema"] == "Eres soporte (v2)."
        and comun.renderizar(prompt["usuario"], {"entrada": "x"}) == "x"
    )


def test_generar_con_ruta_relativa_nombra_bien_la_funcionalidad(tmp_path):
    carpeta = funcionalidad(tmp_path)
    r = run(
        [PY, ROOT / "evals/ia/generar.py", "v1.md", "--simulado", "simulado"],
        cwd=carpeta,
    )
    assert r.returncode == 0 and r.stdout.startswith("soporte/v1:")


def test_generar_simulado_escribe_una_fila_por_caso_y_repeticion(tmp_path):
    carpeta = funcionalidad(tmp_path)
    r = generar(
        carpeta, "v1", "--simulado", carpeta / "simulado", "--repeticiones", "3"
    )
    assert r.returncode == 0, r.stdout + r.stderr
    filas = [
        json.loads(l)
        for l in (carpeta / "resultados/v1.jsonl").read_text().splitlines()
    ]
    assert [f["repeticion"] for f in filas] == [1, 2, 3]
    assert {
        "id",
        "salida",
        "modelo_pedido",
        "stop_reason",
        "coste_usd",
        "latencia_s",
        "huella",
    } <= filas[0].keys()


def test_generar_un_campo_que_falta_en_el_caso_falla_antes_de_gastar(tmp_path):
    carpeta = funcionalidad(tmp_path, cuerpo_usuario="{{entrada}} en {{idioma}}")
    r = generar(carpeta, "v1", "--simulado", carpeta / "simulado")
    assert r.returncode == 2 and "idioma" in r.stdout and "Traceback" not in r.stderr


def test_generar_sin_credenciales_explica_que_hacer(tmp_path):
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("ANTHROPIC_", "CLAUDE_CODE_OAUTH"))
    }
    env["HOME"] = str(tmp_path)  # sin perfiles de `ant auth login`
    r = generar(funcionalidad(tmp_path), "v1", "--concurrencia", "1", env=env)
    assert r.returncode == 2 and "Traceback" not in r.stderr
    assert "ANTHROPIC_API_KEY" in r.stdout or "pip install anthropic" in r.stdout


def test_evaluar_compara_la_version_con_la_anterior_y_detecta_la_mejora(tmp_path):
    carpeta = funcionalidad(tmp_path)
    for v in ("v1", "v2"):
        assert generar(carpeta, v, "--simulado", carpeta / "simulado").returncode == 0
    r = run(
        [
            PY,
            ROOT / "evals/ia/evaluar.py",
            carpeta / "v2.md",
            "--base",
            carpeta / "v1.md",
        ]
    )
    assert (
        r.returncode == 0
        and "Mejoras: c1 (0/3 → 3/3)" in r.stdout
        and "SIMULADAS" in r.stdout
    )


def test_evaluar_rechaza_salidas_de_otra_version_del_prompt(tmp_path):
    carpeta = funcionalidad(tmp_path)
    assert generar(carpeta, "v2", "--simulado", carpeta / "simulado").returncode == 0
    (carpeta / "v2.md").write_text(
        (carpeta / "v2.md").read_text() + "\nUn cambio después de generar.\n"
    )
    r = run([PY, ROOT / "evals/ia/evaluar.py", carpeta / "v2.md"])
    assert r.returncode == 1 and "vuelve a generarlas" in r.stdout


def test_generar_reutiliza_solo_si_nada_ha_cambiado(tmp_path):
    carpeta = funcionalidad(tmp_path)
    simulado = ["--simulado", carpeta / "simulado"]
    generar(carpeta, "v1", *simulado)
    assert "se reutiliza" in generar(carpeta, "v1", *simulado, "--reutilizar").stdout
    assert (
        "se reutiliza"
        not in generar(
            carpeta, "v1", *simulado, "--reutilizar", "--repeticiones", "5"
        ).stdout
    )


def ia_mod(nombre: str):
    sys.path.insert(0, str(ROOT / "evals/ia"))
    return importlib.import_module(nombre)


def test_kappa_cuadratica_valores_conocidos():
    kappa = ia_mod("juez").kappa_cuadratica
    assert kappa([1, 2, 3, 4, 5], [1, 2, 3, 4, 5]) == 1.0
    # = scikit-learn
    assert kappa([1, 2, 3, 4, 5], [1, 2, 3, 4, 4]) == pytest.approx(16 / 17)
    assert kappa([1, 2, 3, 4, 5], [5, 4, 3, 2, 1]) < 0


def test_la_rubrica_por_defecto_define_los_criterios_del_juez():
    juez = ia_mod("juez")
    criterios = juez.criterios_de(
        (ROOT / "evals/ia/rubrica_juez.md").read_text(encoding="utf-8")
    )
    assert criterios == ["fidelidad", "utilidad", "claridad", "tono"]


def juez_simulado(tmp_path, humanas: list[dict]) -> subprocess.CompletedProcess:
    carpeta = funcionalidad(tmp_path)
    (carpeta / "casos.jsonl").write_text(
        "".join(json.dumps({"id": f"c{i}", "entrada": "x"}) + "\n" for i in range(12))
    )
    (carpeta / "simulado/v2.jsonl").write_text(
        "".join(json.dumps({"id": f"c{i}", "salida": "ok"}) + "\n" for i in range(12))
    )
    notas = [
        {
            "id": f"c{i}",
            "fidelidad": 1 + i % 5,
            "utilidad": 1 + (i + 1) % 5,
            "claridad": 1 + i % 5,
            "tono": 1 + (i + 2) % 5,
            "justificacion": "x",
        }
        for i in range(12)
    ]
    (carpeta / "simulado/v2.juez.jsonl").write_text(
        "".join(json.dumps(n) + "\n" for n in notas)
    )
    (carpeta / "humanas.jsonl").write_text(
        "".join(json.dumps(h) + "\n" for h in humanas(notas))
    )
    assert (
        generar(
            carpeta, "v2", "--simulado", carpeta / "simulado", "--repeticiones", "1"
        ).returncode
        == 0
    )
    return run(
        [
            PY,
            ROOT / "evals/ia/juez.py",
            carpeta / "v2.md",
            "--simulado",
            carpeta / "simulado",
            "--calibrar",
        ]
    )


def test_juez_calibrado_cuando_se_parece_a_las_personas(tmp_path):
    r = juez_simulado(
        tmp_path,
        lambda notas: [
            {k: v for k, v in n.items() if k != "justificacion"} for n in notas
        ],
    )
    assert r.returncode == 0 and "CALIBRACIÓN: ✅" in r.stdout
    assert (
        json.loads(
            (tmp_path / "prompts/soporte/resultados/calibracion.json").read_text()
        )["apto"]
        is True
    )


def test_juez_que_no_se_parece_a_las_personas_no_esta_calibrado(tmp_path):
    def al_reves(notas):
        return [
            {
                "id": n["id"],
                **{c: 6 - n[c] for c in ("fidelidad", "utilidad", "claridad", "tono")},
            }
            for n in notas
        ]

    r = juez_simulado(tmp_path, al_reves)
    assert r.returncode == 1 and "CALIBRACIÓN: ❌" in r.stdout


def test_juez_con_pocas_notas_humanas_no_esta_calibrado(tmp_path):
    r = juez_simulado(
        tmp_path,
        lambda notas: [
            {k: v for k, v in n.items() if k != "justificacion"} for n in notas[:5]
        ],
    )
    assert r.returncode == 1 and "al menos 10" in r.stdout


def test_cambiados_evalua_solo_las_versiones_nuevas_contra_la_anterior(tmp_path):
    funcionalidad(tmp_path)
    (tmp_path / "prompts/soporte/v2.md").unlink()
    ejemplo = tmp_path / "prompts/_ejemplo"
    ejemplo.mkdir()
    for args in (
        ["init", "-q", "-b", "main"],
        ["add", "-A"],
        ["-c", "user.email=a@b", "-c", "user.name=t", "commit", "-qm", "v1"],
        ["checkout", "-qb", "rama"],
    ):
        run(["git", *args], cwd=tmp_path)
    funcionalidad(tmp_path / "otra")  # solo para copiar su v2
    (tmp_path / "prompts/soporte/v2.md").write_text(
        (tmp_path / "otra/prompts/soporte/v2.md").read_text()
    )
    # los ejemplos (_…) se saltan
    (ejemplo / "v9.md").write_text("no es un prompt válido")
    for args in (
        ["add", "-A"],
        ["-c", "user.email=a@b", "-c", "user.name=t", "commit", "-qm", "v2"],
    ):
        run(["git", *args], cwd=tmp_path)
    r = run(
        [
            PY,
            ROOT / "evals/ia/cambiados.py",
            "--desde",
            "main",
            "--simulado",
            "--raiz",
            tmp_path,
        ],
        cwd=tmp_path,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert (
        "prompts/soporte/v2.md contra prompts/soporte/v1.md" in r.stdout
        and "1 versiones evaluadas" in r.stdout
    )


def test_cambiados_regenera_una_version_si_el_pr_trae_sus_resultados(tmp_path):
    funcionalidad(tmp_path)
    for args in (
        ["init", "-q", "-b", "main"],
        ["add", "-A"],
        ["-c", "user.email=a@b", "-c", "user.name=t", "commit", "-qm", "base"],
        ["checkout", "-qb", "rama"],
    ):
        run(["git", *args], cwd=tmp_path)
    resultados = tmp_path / "prompts/soporte/resultados"
    resultados.mkdir()
    # "resultados" sin pasar por el modelo
    (resultados / "v2.evaluacion.json").write_text('{"apto": true}')
    for args in (
        ["add", "-A"],
        ["-c", "user.email=a@b", "-c", "user.name=t", "commit", "-qm", "resultados"],
    ):
        run(["git", *args], cwd=tmp_path)
    r = run(
        [
            PY,
            ROOT / "evals/ia/cambiados.py",
            "--desde",
            "main",
            "--simulado",
            "--raiz",
            tmp_path,
        ],
        cwd=tmp_path,
    )
    assert "prompts/soporte/v2.md contra prompts/soporte/v1.md" in r.stdout, (
        r.stdout + r.stderr
    )


def test_cambiados_sin_prompts_cambiados_no_hace_nada(tmp_path):
    for args in (
        ["init", "-q", "-b", "main"],
        [
            "-c",
            "user.email=a@b",
            "-c",
            "user.name=t",
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "x",
        ],
    ):
        run(["git", *args], cwd=tmp_path)
    r = run(
        [PY, ROOT / "evals/ia/cambiados.py", "--desde", "main", "--raiz", tmp_path],
        cwd=tmp_path,
    )
    assert r.returncode == 0 and "nada que evaluar" in r.stdout


def test_make_eval_ia_sin_prompt_explica_el_uso():
    r = run(["make", "-s", "-C", ROOT, "eval-ia"])
    assert r.returncode != 0 and "PROMPT=prompts/" in r.stdout


# El camino real contra la API, con el SDK de verdad y una API falsa a nivel HTTP (sin red ni coste).
def api_falsa(
    peticiones: list,
    texto: str = "No puedo compartirlo.",
    stop_reason: str = "end_turn",
):
    anthropic = pytest.importorskip("anthropic")
    httpx2 = pytest.importorskip("httpx2")

    def responder(request):
        cuerpo = json.loads(request.content)
        peticiones.append((request.headers, cuerpo))
        eventos = [
            {
                "type": "message_start",
                "message": {
                    "id": "m",
                    "type": "message",
                    "role": "assistant",
                    "model": cuerpo["model"],
                    "content": [],
                    "stop_reason": None,
                    "stop_sequence": None,
                    "usage": {"input_tokens": 1000, "output_tokens": 1},
                },
            },
            {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "text", "text": ""},
            },
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": texto},
            },
            {"type": "content_block_stop", "index": 0},
            {
                "type": "message_delta",
                "delta": {"stop_reason": stop_reason, "stop_sequence": None},
                "usage": {"output_tokens": 500},
            },
            {"type": "message_stop"},
        ]
        return httpx2.Response(
            200,
            headers={"content-type": "text/event-stream"},
            text="".join(
                f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in eventos
            ),
        )

    return anthropic.Anthropic(
        api_key="clave-de-prueba",
        max_retries=0,
        http_client=httpx2.Client(transport=httpx2.MockTransport(responder)),
    )


def test_generar_contra_la_api_pide_fallback_y_esfuerzo_y_anota_coste(tmp_path):
    peticiones = []
    cliente = api_falsa(peticiones)
    generar_mod, comun = ia_mod("generar"), ia_mod("comun")
    fila = generar_mod.llamar(
        cliente,
        comun.leer_prompt(funcionalidad(tmp_path) / "v1.md"),
        {"id": "c1", "entrada": "x"},
    )
    cabeceras, cuerpo = peticiones[0]
    assert (
        cabeceras.get("anthropic-beta") == "server-side-fallback-2026-07-01"
        and cuerpo["fallbacks"] == "default"
    )
    assert (
        cuerpo["output_config"] == {"effort": "low"}
        and "temperature" not in cuerpo
        and cuerpo["stream"] is True
    )
    assert fila["salida"] == "No puedo compartirlo." and fila[
        "coste_usd"
    ] == pytest.approx((1000 * 4 + 500 * 20) / 1e6)


def test_generar_sin_fallback_para_modelos_que_no_lo_tienen(tmp_path):
    peticiones = []
    generar_mod, comun = ia_mod("generar"), ia_mod("comun")
    prompt = comun.leer_prompt(funcionalidad(tmp_path) / "v1.md") | {
        "modelo": "claude-haiku-5-5"
    }
    generar_mod.llamar(api_falsa(peticiones), prompt, {"id": "c1", "entrada": "x"})
    cabeceras, cuerpo = peticiones[0]
    assert "fallbacks" not in cuerpo and "server-side-fallback" not in cabeceras.get(
        "anthropic-beta", ""
    )


def test_generar_descarta_el_texto_de_una_negativa(tmp_path):
    generar_mod, comun = ia_mod("generar"), ia_mod("comun")
    fila = generar_mod.llamar(
        api_falsa([], texto="Parcial…", stop_reason="refusal"),
        comun.leer_prompt(funcionalidad(tmp_path) / "v1.md"),
        {"id": "c1", "entrada": "x"},
    )
    assert fila["stop_reason"] == "refusal" and fila["salida"] == ""


# ── Evals del agente (evals/agente/run.py) ──────────────────────────────────────────────────────
def runner():
    spec_ = importlib.util.spec_from_file_location(
        "runner_agente", ROOT / "evals/agente/run.py"
    )
    mod = importlib.util.module_from_spec(spec_)
    spec_.loader.exec_module(mod)
    return mod


def test_runner_puede_editar_sin_nadie_que_apruebe():
    # En `claude -p` se deniega todo lo que pediría permiso: sin este modo no podría editar nada.
    argv = runner().comando("/implementar T-001")
    assert (
        "--permission-mode" in argv
        and argv[argv.index("--permission-mode") + 1] == "acceptEdits"
    )


def test_runner_no_carga_servidores_mcp_del_proyecto():
    # En `claude -p` los servidores de .mcp.json se cargan sin preguntar: un eval no debe llegar a producción.
    assert "--strict-mcp-config" in runner().comando("/implementar T-001")


def test_runner_no_se_queda_esperando_aprobacion_del_plan():
    prompt = runner().comando("/implementar T-001")[2]
    assert "aprobado" in prompt.lower()


# ── Configuración (.claude/settings.json y workflows) ───────────────────────────────────────────
def settings() -> dict:
    return json.loads((ROOT / ".claude/settings.json").read_text(encoding="utf-8"))


def test_hooks_de_guardrail_fallan_cerrado():
    for evento in ("PreToolUse", "ConfigChange"):
        for grupo in settings()["hooks"][evento]:
            for hook in grupo["hooks"]:
                assert hook.get("onFailure") == "block", (evento, grupo.get("matcher"))


def test_los_notebooks_pasan_por_el_guardrail_de_archivos():
    matchers = [g["matcher"] for g in settings()["hooks"]["PreToolUse"]]
    assert any("NotebookEdit" in m.split("|") for m in matchers)


def test_el_contexto_de_la_tarea_vuelve_en_cada_inicio_de_sesion():
    # sin matcher: al empezar, al retomar, tras /clear y tras compactar
    grupos = settings()["hooks"]["SessionStart"]
    assert any(
        "matcher" not in g and any("contexto.py" in h["command"] for h in g["hooks"])
        for g in grupos
    )


def test_el_guardia_de_configuracion_esta_registrado():
    comandos = [
        h["command"] for g in settings()["hooks"]["ConfigChange"] for h in g["hooks"]
    ]
    assert any("guard_config.py" in c for c in comandos)


def test_no_hay_reglas_write_que_nunca_se_aplican():
    # Claude Code solo compara rutas con reglas Edit(...) y Read(...); Write(...) se acepta pero no aplica.
    assert not [r for r in settings()["permissions"]["deny"] if r.startswith("Write(")]


@pytest.mark.parametrize(
    "regla",
    [
        "Edit(./.claude/**)",
        "Edit(./.github/workflows/**)",
        "Edit(./tests/test_guardrails.py)",
        "Edit(./tests/test_reglas_proyecto.py)",
        "Edit(./tests/test_kit.py)",
        "Read(~/.ssh/**)",
        "Read(~/.aws/**)",
    ],
)
def test_rutas_sensibles_denegadas(regla):
    assert regla in settings()["permissions"]["deny"]


WORKFLOWS = sorted(p.name for p in (ROOT / ".github/workflows").glob("*.yml"))


@pytest.mark.parametrize("workflow", WORKFLOWS)
def test_workflows_con_permisos_minimos(workflow):
    yaml = pytest.importorskip("yaml")
    datos = yaml.safe_load(
        (ROOT / ".github/workflows" / workflow).read_text(encoding="utf-8")
    )
    assert datos.get("permissions") == {"contents": "read"}


@pytest.mark.parametrize("workflow", WORKFLOWS)
def test_acciones_fijadas_por_sha_y_sin_credenciales_persistentes(workflow):
    texto = (ROOT / ".github/workflows" / workflow).read_text(encoding="utf-8")
    usos = re.findall(r"uses:\s*(\S+)", texto)
    assert usos and all(
        re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", u) for u in usos
    ), usos
    assert texto.count("actions/checkout@") == texto.count("persist-credentials: false")


@pytest.mark.parametrize(
    "comando",
    [
        "implementar",
        "cierre",
        "descubrir",
        "adr",
        "diagrama",
        "lanzamiento",
        "incidente",
    ],
)
def test_cada_etapa_tiene_su_comando(comando):
    texto = (ROOT / ".claude/commands" / f"{comando}.md").read_text(encoding="utf-8")
    assert re.match(r"---\ndescription: .+\n(argument-hint: .+\n)?---\n", texto)


def test_las_referencias_a_plantillas_apuntan_a_archivos_que_existen():
    textos = " ".join(
        p.read_text(encoding="utf-8")
        for p in [
            *(ROOT / "docs").rglob("*.md"),
            *(ROOT / ".claude/commands").glob("*.md"),
        ]
    )
    for ruta in set(
        re.findall(r"`(docs/plantillas/[\w-]+\.md|docs/checklists/[\w-]+\.md)`", textos)
    ):
        assert (ROOT / ruta).exists(), ruta


def test_dependabot_vigila_las_acciones():
    yaml = pytest.importorskip("yaml")
    datos = yaml.safe_load(
        (ROOT / ".github/dependabot.yml").read_text(encoding="utf-8")
    )
    assert any(u["package-ecosystem"] == "github-actions" for u in datos["updates"])


def test_evals_con_coste_inactivos_hasta_configurarlos():
    yaml = pytest.importorskip("yaml")
    trabajos = yaml.safe_load(
        (ROOT / ".github/workflows/evals.yml").read_text(encoding="utf-8")
    )["jobs"]
    assert all(
        "EVALS_ACTIVOS" in str(t.get("if", ""))
        for n, t in trabajos.items()
        if n.startswith("eval-")
    )


def test_despliegue_inactivo_hasta_configurarlo():
    yaml = pytest.importorskip("yaml")
    datos = yaml.safe_load(
        (ROOT / ".github/workflows/deploy.yml").read_text(encoding="utf-8")
    )
    assert "DESPLIEGUE_ACTIVO" in str(datos["jobs"]["verificar"].get("if", ""))


# ── Instalación y actualización (instalar.sh, solo dentro del propio kit) ─────────────────────
solo_en_el_kit = pytest.mark.skipif(
    not (ROOT / "instalar.sh").exists(), reason="instalar.sh solo existe en el kit"
)


@solo_en_el_kit
def test_instalar_no_sobrescribe_lo_existente(tmp_path):
    assert run(["bash", ROOT / "instalar.sh", tmp_path]).returncode == 0
    (tmp_path / "CLAUDE.md").write_text("mío\n")
    run(["bash", ROOT / "instalar.sh", tmp_path])
    assert (tmp_path / "CLAUDE.md").read_text() == "mío\n"


@solo_en_el_kit
def test_instalar_ignora_las_propuestas_y_copias_en_git(tmp_path):
    run(["bash", ROOT / "instalar.sh", tmp_path])
    ignorados = (tmp_path / ".gitignore").read_text().splitlines()
    assert ".kit/" in ignorados and ".kit-backup/" in ignorados
    # el mapa del código se reconstruye en local en segundos: no va al repositorio
    assert "graphify-out/" in ignorados and (tmp_path / ".graphifyignore").exists()
    # sin esto, git status, el alcance y el escaneo de secretos verían miles de archivos de dependencias
    assert ".venv/" in ignorados and "node_modules/" in ignorados


@solo_en_el_kit
def test_kit_ignorar_evita_que_vuelva_lo_que_el_proyecto_quito(tmp_path):
    (tmp_path / ".kit-ignorar").write_text(
        "# no usamos el ejemplo\nprompts/_ejemplo/\ntests/e2e/*\n"
    )
    assert run(["bash", ROOT / "instalar.sh", tmp_path]).returncode == 0
    assert (
        not (tmp_path / "prompts/_ejemplo").exists()
        and not (tmp_path / "tests/e2e").exists()
    )
    assert (tmp_path / "prompts/README.md").exists()
    assert run(["bash", ROOT / "instalar.sh", "--actualizar", tmp_path]).returncode == 0
    assert not (tmp_path / "prompts/_ejemplo").exists()


@solo_en_el_kit
def test_actualizar_respeta_lo_del_proyecto_y_guarda_copia(tmp_path):
    run(["bash", ROOT / "instalar.sh", tmp_path])
    reglas = tmp_path / ".claude/hooks/reglas_proyecto.py"
    reglas.write_text("BASH = [(r'x', 'regla del proyecto')]\nARCHIVOS = []\n")
    hook = tmp_path / ".claude/hooks/guard_bash.py"
    hook.write_text(hook.read_text() + "\n# cambio local\n")
    r = run(["bash", ROOT / "instalar.sh", "--actualizar", tmp_path])
    assert r.returncode == 0, r.stdout + r.stderr
    assert "regla del proyecto" in reglas.read_text()
    assert hook.read_text() == (ROOT / ".claude/hooks/guard_bash.py").read_text()
    assert list(tmp_path.glob(".kit-backup/*/.claude/hooks/guard_bash.py"))
    assert (tmp_path / ".kit-version").read_text().strip() == (
        ROOT / "VERSION"
    ).read_text().strip()


@solo_en_el_kit
def test_actualizar_se_niega_si_hay_reglas_en_el_formato_antiguo(tmp_path):
    run(["bash", ROOT / "instalar.sh", tmp_path])
    hook = tmp_path / ".claude/hooks/guard_bash.py"
    hook.write_text(
        "PROYECTO: list[tuple[str, str]] = [\n    (r'x', 'regla antigua'),\n]\n"
    )
    r = run(["bash", ROOT / "instalar.sh", "--actualizar", tmp_path])
    assert r.returncode != 0 and "reglas_proyecto.py" in (r.stdout + r.stderr)
    assert "regla antigua" in hook.read_text()


# ── Contexto que no se pierde: bitácora (alcance.py --nota) y hook de inicio de sesión ──────────
def test_iniciar_y_anotar_escriben_la_bitacora_de_la_spec(tmp_path):
    r = proyecto_con_tarea(tmp_path)
    assert alcance(r, "--iniciar", "T-002-1").returncode == 0
    nota = alcance(
        r, "--nota", "test en rojo\npor la razón | esperada", "--siguiente", "el cobro"
    )
    assert nota.returncode == 0, nota.stdout
    bitacora = (r / "specs/002-pagos/progreso.md").read_text().splitlines()
    assert bitacora[0] == "# Progreso de 002-pagos"
    assert re.match(r"- \d{4}-\d\d-\d\d \d\d:\d\d · T-002-1 · iniciada$", bitacora[-2])
    assert bitacora[-1].endswith(
        "· T-002-1 · test en rojo por la razón / esperada · siguiente: el cobro"
    )
    assert (
        alcance(r).returncode == 0
    )  # la bitácora está en la carpeta de la spec: dentro del alcance


def test_volver_a_iniciar_una_tarea_la_marca_como_retomada(tmp_path):
    r = proyecto_con_tarea(tmp_path)
    alcance(r, "--iniciar", "T-002-1")
    alcance(r, "--iniciar", "T-002-1")
    ultima = (r / "specs/002-pagos/progreso.md").read_text().splitlines()[-1]
    assert ultima.endswith("· T-002-1 · retomada")


def test_anotar_sin_tarea_activa_falla_con_un_mensaje_claro(tmp_path):
    r = alcance(repo(tmp_path), "--nota", "algo")
    assert r.returncode == 1 and "--iniciar" in r.stdout


def contexto(raiz, source="startup", entrada=None) -> subprocess.CompletedProcess:
    datos = entrada if entrada is not None else json.dumps({"source": source})
    return run(
        [PY, ROOT / ".claude/hooks/contexto.py"],
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(raiz)},
        entrada=datos,
    )


def test_contexto_sin_specs_dice_por_donde_empezar(tmp_path):
    r = contexto(repo(tmp_path))
    assert r.returncode == 0 and "Aún no hay specs" in r.stdout


def test_contexto_sin_tarea_activa_propone_la_siguiente_pendiente(tmp_path):
    r = contexto(proyecto_con_tarea(tmp_path))
    assert "Sin tarea activa" in r.stdout and "/implementar T-002-1" in r.stdout


def test_contexto_devuelve_la_tarea_con_requisitos_archivos_cambios_y_ultima_nota(
    tmp_path,
):
    r = proyecto_con_tarea(tmp_path)
    (r / "specs/002-pagos/spec.md").write_text(
        "# SPEC-002\n\nEstado: APROBADA\n\n| ID | Requisito | Prioridad |\n|---|---|---|\n"
        "| REQ-P-001 | CUANDO se repite un cobro, EL SISTEMA DEBE cobrar una sola vez. | DEBE |\n"
    )
    alcance(r, "--iniciar", "T-002-1")
    alcance(r, "--nota", "test en rojo", "--siguiente", "clave de idempotencia")
    (r / "src").mkdir()
    (r / "src/pagos.py").write_text("x = 1\n")
    (r / "README.md").write_text(
        "cambiado\n"
    )  # versionado: primera línea de git status
    salida = contexto(r, "compact").stdout
    assert "tras compactar" in salida
    assert (
        "Tarea activa: T-002-1 «Cobro idempotente» · specs/002-pagos (APROBADA)"
        in salida
    )
    assert (
        "REQ-P-001: CUANDO se repite un cobro, EL SISTEMA DEBE cobrar una sola vez."
        in salida
    )
    assert "Archivos permitidos: src/pagos.py, tests/test_pagos.py" in salida
    assert "Cambios sin commit: README.md," in salida and "src/" in salida
    assert (
        "test en rojo" in salida and "Siguiente paso: clave de idempotencia" in salida
    )


def test_contexto_expande_los_rangos_de_requisitos(tmp_path):
    r = repo(tmp_path)
    d = r / "specs/004-auditoria"
    d.mkdir(parents=True)
    (d / "spec.md").write_text(
        "# SPEC-004\n\nEstado: APROBADA\n\n| REQ-AUD-001 | Se audita la lectura. | DEBE |\n"
        "| REQ-AUD-002 | La auditoría es inmutable. | DEBE |\n"
    )
    (d / "tasks.md").write_text(
        "| ID | Tarea | Requisitos | Archivos permitidos | Estado |\n|---|---|---|---|---|\n"
        "| T-004-1 | Auditoría | REQ-AUD-001..002 | `app/repo.py` | ⏳ |\n"
    )
    alcance(r, "--iniciar", "T-004-1")
    salida = contexto(r).stdout
    assert "REQ-AUD-001: Se audita la lectura." in salida
    assert "REQ-AUD-002: La auditoría es inmutable." in salida


def mapa_falso(raiz, commit: str) -> None:
    salida = raiz / "graphify-out"
    salida.mkdir(exist_ok=True)
    (salida / "graph.json").write_text(
        json.dumps({"nodes": [], "links": [], "built_at_commit": commit})
    )


def test_contexto_dice_si_el_mapa_del_codigo_esta_al_dia(tmp_path):
    r = repo(tmp_path)
    assert "Mapa del código" not in contexto(r).stdout  # sin mapa no dice nada
    head = run(["git", "rev-parse", "HEAD"], cwd=r).stdout.strip()
    mapa_falso(r, head)
    assert "Mapa del código (graphify-out/, al día)" in contexto(r).stdout
    (r / "nuevo.py").write_text("x = 1\n")
    os.utime(r / "nuevo.py", (9e9, 9e9))  # cambiado después del mapa
    assert "desactualizado (nuevo.py cambió después)" in contexto(r).stdout
    mapa_falso(r, "0" * 40)
    assert "desactualizado (es del commit 0000000" in contexto(r).stdout


def test_contexto_nunca_impide_empezar_la_sesion(tmp_path):
    r = repo(tmp_path)
    (r / ".kit").mkdir()
    (r / ".kit/tarea-actual").write_text("{esto no es json")
    (r / "CLAUDE.md").write_bytes(b"\xff\xfe basura")
    for entrada in ("", "[]", "{roto"):
        resultado = contexto(r, entrada=entrada)
        assert resultado.returncode == 0 and resultado.stdout.strip()


def test_contexto_no_pasa_del_limite_de_claude_code(tmp_path):
    r = proyecto_con_tarea(tmp_path)
    filas = "".join(f"| REQ-P-{n:03d} | {'x' * 900} | DEBE |\n" for n in range(1, 30))
    (r / "specs/002-pagos/spec.md").write_text("# S\n\nEstado: APROBADA\n\n" + filas)
    (r / "specs/002-pagos/tasks.md").write_text(
        "| ID | Tarea | Requisitos | Archivos permitidos | Estado |\n|---|---|---|---|---|\n"
        "| T-002-1 | Todo | REQ-P-001..029 | `src/a.py` | ⏳ |\n"
    )
    alcance(r, "--iniciar", "T-002-1")
    for n in range(40):
        alcance(r, "--nota", "y" * 400, "--siguiente", "z" * 400)
    assert len(contexto(r).stdout) <= 6100


# ── Mapa del código con graphify (opcional) ─────────────────────────────────────────────────────
def graphify_falso(tmp_path, version: str = "0.9.93") -> pathlib.Path:
    """Un `graphify` de pega que apunta con qué argumentos y entorno lo llaman."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    falso = bin_dir / "graphify"
    falso.write_text(
        "#!/bin/sh\n"
        f'[ "$1" = "--version" ] && echo "graphify {version}" && exit 0\n'
        'echo "$* backend=$GRAPHIFY_BACKEND" >> llamadas.log\n'
    )
    falso.chmod(0o755)
    return bin_dir


def make_mapa(cwd, path: str) -> subprocess.CompletedProcess:
    return run(
        ["make", "--no-print-directory", "-f", ROOT / "Makefile", "mapa"],
        cwd=cwd,
        env={**os.environ, "PATH": path},
    )


def test_make_mapa_sin_graphify_explica_como_instalarlo_y_no_falla(tmp_path):
    r = make_mapa(tmp_path, "/usr/bin:/bin")
    assert r.returncode == 0 and "uv tool install graphifyy==" in r.stdout


def test_make_mapa_actualiza_solo_el_codigo_sin_modelo(tmp_path):
    bin_dir = graphify_falso(tmp_path)
    r = make_mapa(tmp_path, f"{bin_dir}:/usr/bin:/bin")
    assert r.returncode == 0 and "Aviso" not in r.stdout
    assert (tmp_path / "llamadas.log").read_text() == "update . backend=none\n"


def test_make_mapa_avisa_si_la_version_no_es_la_probada(tmp_path):
    bin_dir = graphify_falso(tmp_path, "0.1.0")
    assert (
        "Aviso: tienes graphify 0.1.0"
        in make_mapa(tmp_path, f"{bin_dir}:/usr/bin:/bin").stdout
    )


def test_el_mapa_del_codigo_no_entra_en_secretos_ni_arquitectura(tmp_path):
    salida = tmp_path / "graphify-out"
    salida.mkdir()
    (salida / "graph.json").write_text('{"label": "password = \'supersecreta123\'"}')
    (salida / "x.py").write_text("import sqlalchemy\n")
    assert run([PY, ROOT / "evals/secretos.py", "--raiz", tmp_path]).returncode == 0
    modulo = importlib.util.spec_from_file_location(
        "arq", ROOT / "evals/arquitectura.py"
    )
    arq = importlib.util.module_from_spec(modulo)
    modulo.loader.exec_module(arq)
    assert not list(arq.fuentes(tmp_path))


# ── Portabilidad: el Python del proyecto y el Python 3.9 de macOS ───────────────────────────────
def test_make_usa_el_python_de_venv_aunque_no_este_activado(tmp_path):
    # En macOS con Homebrew no se puede instalar pytest fuera de un entorno (PEP 668), y el make 3.81
    # de macOS busca los comandos simples con el PATH original: por eso el Makefile usa $(PY).
    bin_dir = tmp_path / ".venv/bin"
    bin_dir.mkdir(parents=True)
    falso = bin_dir / "python"
    falso.write_text('#!/bin/sh\necho "$*" >> llamadas.log\n')
    falso.chmod(0o755)
    r = run(
        ["make", "--no-print-directory", "-f", ROOT / "Makefile", "test"], cwd=tmp_path
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert (tmp_path / "llamadas.log").read_text() == (
        "-m pytest -q --junitxml=.kit/resultados/junit.xml\n"
    )


def test_make_sin_venv_usa_python3(tmp_path):
    r = run(
        ["make", "-n", "--no-print-directory", "-f", ROOT / "Makefile", "test"],
        cwd=tmp_path,
    )
    assert "python3 -m pytest -q --junitxml=.kit/resultados/junit.xml" in r.stdout


def anotaciones_con_union(arbol) -> bool:
    import ast

    anotaciones = []
    for n in ast.walk(arbol):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            a = n.args
            for arg in [*a.posonlyargs, *a.args, *a.kwonlyargs, a.vararg, a.kwarg]:
                if arg is not None and arg.annotation is not None:
                    anotaciones.append(arg.annotation)
            if n.returns is not None:
                anotaciones.append(n.returns)
        elif isinstance(n, ast.AnnAssign):
            anotaciones.append(n.annotation)
    return any(
        isinstance(x, ast.BinOp) and isinstance(x.op, ast.BitOr)
        for a in anotaciones
        for x in ast.walk(a)
    )


def test_el_kit_funciona_con_el_python_39_de_macos():
    # /usr/bin/python3 de macOS es 3.9: `str | None` en una anotación revienta al importar el módulo
    # (antes del try que hace fallar cerrado al hook) salvo con `from __future__ import annotations`.
    import ast

    sin_futuro = []
    for ruta in sorted(ROOT.rglob("*.py")):
        if {"__pycache__", ".venv", "worktrees"} & set(ruta.parts):
            continue
        texto = ruta.read_text(encoding="utf-8")
        if anotaciones_con_union(ast.parse(texto)) and (
            "from __future__ import annotations" not in texto
        ):
            sin_futuro.append(ruta.relative_to(ROOT).as_posix())
    assert sin_futuro == [], sin_futuro


def test_implementar_marca_la_tarea_como_terminada():
    # Sin el ✅ en tasks.md, el contexto de inicio, /kit y --solapes seguirían ofreciéndola como pendiente.
    texto = (ROOT / ".claude/commands/implementar.md").read_text(encoding="utf-8")
    assert "⏳ → ✅" in texto and "tasks.md" in texto


def test_los_secretos_de_entorno_no_se_leen_pero_el_ejemplo_si():
    # En Claude Code un deny gana siempre a un allow: con Read(./.env.*) el agente no podía ni crear
    # .env.example, que se versiona y no lleva secretos.
    import fnmatch

    lecturas = [
        r[len("Read(./") : -1]
        for r in settings()["permissions"]["deny"]
        if r.startswith("Read(./")
    ]
    for secreto in (".env", ".env.local", ".env.production", ".env.development.local"):
        assert any(fnmatch.fnmatch(secreto, p) for p in lecturas), secreto
    for ejemplo in (".env.example", ".env.sample", ".env.template"):
        assert not any(fnmatch.fnmatch(ejemplo, p) for p in lecturas), ejemplo
