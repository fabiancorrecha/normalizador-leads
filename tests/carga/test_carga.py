"""Requisitos de rendimiento como tests: cada test cita su requisito y lanza k6 contra URL_ENTORNO.

Sin URL_ENTORNO se saltan con la marca [entorno]: `make check` no puede probarlos y la cobertura los
muestra como "se verifica en entorno", ni cubiertos ni fallidos. Se ejecutan con
`make carga URL_ENTORNO=https://staging…` (deploy.yml lo hace contra staging). Con URL_ENTORNO y sin
k6, fallan: un gate que no puede medir no aprueba.
"""

import os
import pathlib
import shutil
import subprocess

import pytest

AQUI = pathlib.Path(__file__).resolve().parent
URL_ENTORNO = os.environ.get("URL_ENTORNO", "").rstrip("/")
pytestmark = pytest.mark.skipif(
    not URL_ENTORNO, reason="[entorno] necesita URL_ENTORNO (make carga URL_ENTORNO=…)"
)


def k6(escenario: str, **variables) -> subprocess.CompletedProcess:
    if not shutil.which("k6"):
        pytest.fail(
            "Hay URL_ENTORNO pero falta k6: https://grafana.com/docs/k6/latest/set-up/install-k6/"
        )
    entorno = (
        os.environ
        | {"URL_ENTORNO": URL_ENTORNO}
        | {k: str(v) for k, v in variables.items()}
    )
    return subprocess.run(
        ["k6", "run", "--quiet", str(AQUI / escenario)],
        env=entorno,
        capture_output=True,
        text=True,
        check=False,
    )


# Renombra el test con el ID de su requisito (test_REQ_<ÁREA>_<NÚMERO>_…, p. ej. para REQ-INF-001:
# test_REQ_INF_…_p95_bajo_300ms con el número real) y pon sus cifras.
def test_flujo_critico_p95_bajo_umbral():
    r = k6(
        "escenario.js",
        RUTA="/",
        USUARIOS=20,
        DURACION="30s",
        P95_MS=300,
        ERRORES_MAX=0.01,
    )
    assert r.returncode == 0, (
        f"k6 no cumple los umbrales:\n{r.stdout[-3000:]}\n{r.stderr[-2000:]}"
    )
