"""Pone el proyecto en marcha con un solo comando: crea `.venv/` si no existe, instala las
dependencias y normaliza los exports de ejemplo (las clínicas A y B del encargo y la C sintética).

    python3 lanzar.py                      # extractor por diccionario: sin red y sin coste
    python3 lanzar.py --extractor claude   # con Claude (clave en .env.dev); cuesta dinero
    python3 lanzar.py --salida otra/carpeta

Es un envoltorio de la CLI (`python -m normalizador`) sin reglas del producto: lo que hace cada
carga está en `src/normalizador/` y en el README.
"""

# Lo exige tests/test_kit.py en todo módulo con uniones `X | None` en las anotaciones.
from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

RAIZ = pathlib.Path(__file__).resolve().parent
VENV = RAIZ / ".venv"
PYTHON_DEL_VENV = VENV / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
REQUISITOS = RAIZ / "requirements-dev.txt"
VERSION_MINIMA = (3, 13)  # la de pyproject.toml
SALIDA_POR_DEFECTO = RAIZ / "salida"
# Los mismos nombres que `--extractor` en la CLI (src/normalizador/cli.py).
EXTRACTORES = ("diccionario", "claude")
EXTRACTOR_CLAUDE = "claude"
# Los exports de ejemplo: A y B vienen con el encargo; C es la tercera clínica, sintética.
EJEMPLOS = (
    ("clinica_a", "docs/clinica_a_leads.json"),
    ("clinica_b", "docs/clinica_b_leads.json"),
    ("clinica_c", "tests/datos/clinica_c_leads.json"),
)
FALLO = 1


def main(argumentos: list[str] | None = None) -> int:
    opciones = leer_argumentos(argumentos)
    if not PYTHON_DEL_VENV.exists() and sys.version_info < VERSION_MINIMA:
        version = ".".join(str(parte) for parte in VERSION_MINIMA)
        return abortar(
            f"hace falta Python {version} o superior para crear {VENV.name}/ y este script corre "
            f"con {sys.version.split()[0]}: ejecútalo con `python{version} lanzar.py`"
        )
    try:
        preparar_entorno()
    except subprocess.CalledProcessError as error:
        return abortar(f"no se pudo preparar el entorno (código {error.returncode})")
    if opciones.extractor == EXTRACTOR_CLAUDE:
        avisar(
            "--extractor claude llama al modelo: necesita ANTHROPIC_API_KEY (o .env / .env.dev) "
            "y cuesta dinero"
        )
    salida = opciones.salida.resolve()
    for clinica, entrada in EJEMPLOS:
        destino = salida / clinica
        paso(f"{clinica}: {entrada} → {ruta_corta(destino)}")
        codigo = normalizar(clinica, entrada, destino, opciones.extractor)
        if codigo != 0:
            return abortar(f"la carga de {clinica} terminó con código {codigo}; no se sigue")
    print()
    print(
        f"Listo. En {ruta_corta(salida)}/<clinica>/ están leads.jsonl, cuarentena.jsonl e "
        "informe.json; el histórico acumulado de calidad, en datos/historico_calidad.jsonl."
    )
    print(
        "Siguiente: `make check` (tests, lint, arquitectura y cobertura de requisitos) y el README."
    )
    return 0


def leer_argumentos(argumentos: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="lanzar.py",
        description="Prepara el entorno y normaliza los exports de ejemplo (clínicas A, B y C).",
    )
    parser.add_argument(
        "--extractor",
        choices=EXTRACTORES,
        default=EXTRACTORES[0],
        help="cómo se extraen los campos del texto: diccionario (por defecto, sin red) o claude "
        "(modelo; cuesta dinero y necesita la clave de la API)",
    )
    parser.add_argument(
        "--salida",
        type=pathlib.Path,
        default=SALIDA_POR_DEFECTO,
        help="carpeta de salida; cada clínica escribe en <salida>/<clinica>/ "
        "(por defecto, salida/)",
    )
    return parser.parse_args(argumentos)


def preparar_entorno() -> None:
    """Crea `.venv/` con el Python que ejecuta este script e instala `requirements-dev.txt`. Si el
    paquete ya importa en el entorno, no hace nada."""
    if not PYTHON_DEL_VENV.exists():
        paso(f"creando el entorno virtual en {VENV.name}/ con {sys.executable}")
        ejecutar([sys.executable, "-m", "venv", str(VENV)], check=True)
    if not paquete_instalado():
        paso(f"instalando las dependencias de {REQUISITOS.name}")
        ejecutar(
            [str(PYTHON_DEL_VENV), "-m", "pip", "install", "--quiet", "-r", str(REQUISITOS)],
            check=True,
        )


def paquete_instalado() -> bool:
    comando = [str(PYTHON_DEL_VENV), "-c", "import normalizador"]
    return ejecutar(comando, capture_output=True).returncode == 0


def normalizar(clinica: str, entrada: str, salida: pathlib.Path, extractor: str) -> int:
    """Una carga con la CLI. Sus logs (solo datos técnicos) y su resumen salen tal cual."""
    comando = [
        str(PYTHON_DEL_VENV),
        "-m",
        "normalizador",
        "--clinica",
        clinica,
        "--entrada",
        entrada,
        "--salida",
        ruta_corta(salida),
        "--extractor",
        extractor,
    ]
    return ejecutar(comando).returncode


def ejecutar(comando: list[str], **opciones: bool) -> subprocess.CompletedProcess[bytes]:
    """Desde la raíz del proyecto, para que valgan las rutas por defecto de la CLI (`config/`,
    `prompts/`, `datos/`). Los comandos salen de constantes de este archivo y de argumentos ya
    validados por argparse, y nunca pasan por un shell."""
    return subprocess.run(comando, cwd=RAIZ, **opciones)  # noqa: S603


def ruta_corta(ruta: pathlib.Path) -> str:
    """Relativa a la raíz del proyecto cuando está dentro; si no, absoluta."""
    return str(ruta.relative_to(RAIZ)) if ruta.is_relative_to(RAIZ) else str(ruta)


def paso(texto: str) -> None:
    print(f"→ {texto}", flush=True)


def avisar(texto: str) -> None:
    print(f"aviso: {texto}", file=sys.stderr, flush=True)


def abortar(motivo: str) -> int:
    print(f"error: {motivo}", file=sys.stderr, flush=True)
    return FALLO


if __name__ == "__main__":
    sys.exit(main())
