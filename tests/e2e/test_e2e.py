"""Requisitos de interfaz como tests: recorridos críticos y accesibilidad (WCAG 2.1 AA, con axe-core).

Se ejecutan con Playwright contra URL_ENTORNO: `make e2e URL_ENTORNO=https://staging…` (deploy.yml lo
hace contra staging). Necesitan `pip install pytest playwright` y `python -m playwright install chromium`.
Sin URL_ENTORNO se saltan con la marca [entorno] y la cobertura los muestra como "se verifica en
entorno". Con URL_ENTORNO y sin Playwright, fallan: un gate que no puede medir no aprueba.
"""

import hashlib
import io
import os
import pathlib
import tarfile
import urllib.request

import pytest

URL_ENTORNO = os.environ.get("URL_ENTORNO", "").rstrip("/")
pytestmark = pytest.mark.skipif(
    not URL_ENTORNO, reason="[entorno] necesita URL_ENTORNO (make e2e URL_ENTORNO=…)"
)

# axe-core fijado por versión y huella: si lo descargado no coincide, el test falla en vez de ejecutarlo.
AXE_VERSION = "4.14.0"
AXE_SHA256 = "20c09fe157a8a34a30e241aaa1fcdade657734f08ab379ecfbeb7d45cc46e878"  # package/axe.min.js
AXE_URL = f"https://registry.npmjs.org/axe-core/-/axe-core-{AXE_VERSION}.tgz"
AXE_CACHE = (
    pathlib.Path(__file__).resolve().parents[2]
    / ".kit"
    / "cache"
    / f"axe-core-{AXE_VERSION}.min.js"
)
WCAG = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]


def axe_core() -> str:
    if not AXE_CACHE.exists():
        with urllib.request.urlopen(AXE_URL, timeout=60) as respuesta:
            datos_paquete = respuesta.read()
        with tarfile.open(fileobj=io.BytesIO(datos_paquete), mode="r:gz") as paquete:
            contenido = paquete.extractfile("package/axe.min.js").read()
        AXE_CACHE.parent.mkdir(parents=True, exist_ok=True)
        AXE_CACHE.write_bytes(contenido)
    datos = AXE_CACHE.read_bytes()
    if hashlib.sha256(datos).hexdigest() != AXE_SHA256:
        AXE_CACHE.unlink()
        pytest.fail(
            f"axe-core {AXE_VERSION} no coincide con la huella fijada: no se ejecuta código no verificado."
        )
    return datos.decode("utf-8")


@pytest.fixture(scope="module")
def navegador():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        pytest.fail(
            "Hay URL_ENTORNO pero falta Playwright: pip install playwright && python -m playwright install chromium"
        )
    with sync_playwright() as p:
        navegador = p.chromium.launch()
        yield navegador
        navegador.close()


@pytest.fixture
def pagina(navegador):
    contexto = navegador.new_context(base_url=URL_ENTORNO)
    yield contexto.new_page()
    contexto.close()


def problemas_de_accesibilidad(pagina) -> list[str]:
    """Violaciones graves o críticas de WCAG 2.1 AA en la página actual."""
    pagina.add_script_tag(content=axe_core())
    resultado = pagina.evaluate(
        "tags => axe.run(document, {runOnly: {type: 'tag', values: tags}})", WCAG
    )
    return [
        f"{v['id']} ({v['impact']}): {v['help']} — {len(v['nodes'])} elemento(s)"
        for v in resultado["violations"]
        if v["impact"] in ("serious", "critical")
    ]


# Renombra cada test con el ID de su requisito (test_REQ_<ÁREA>_<NÚMERO>_…) y adapta la ruta y los pasos.
def test_pagina_principal_carga_y_es_accesible(pagina):
    respuesta = pagina.goto("/")
    assert respuesta is not None and respuesta.ok, (
        f"/ respondió {respuesta.status if respuesta else 'nada'}"
    )
    problemas = problemas_de_accesibilidad(pagina)
    assert not problemas, "Accesibilidad (WCAG 2.1 AA):\n" + "\n".join(problemas)
