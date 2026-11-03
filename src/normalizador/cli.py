"""Raíz de composición: lee los argumentos, conecta el pipeline con sus adaptadores y lo ejecuta.

En el esqueleto (T-001-1) solo comprueba que el export es JSON y escribe una salida sin leads; el
pipeline con el perfil de la clínica llega en T-001-4.
"""

# Lo exige tests/test_kit.py en todo módulo con uniones `X | None` en las anotaciones.
from __future__ import annotations

import argparse
import json
import pathlib

ARCHIVO_LEADS = "leads.jsonl"
ARCHIVO_INFORME = "informe.json"


def main(argumentos: list[str] | None = None) -> int:
    opciones = leer_argumentos(argumentos)
    comprobar_export(opciones.entrada)
    escribir_salida_sin_leads(opciones.salida, perfil=opciones.clinica, entrada=opciones.entrada)
    return 0


def leer_argumentos(argumentos: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="normalizador",
        description="Normaliza el export de leads de una clínica al esquema común.",
    )
    parser.add_argument(
        "--clinica", required=True, help="perfil de la clínica; es el `source` de sus leads"
    )
    parser.add_argument(
        "--entrada", required=True, type=pathlib.Path, help="export de la clínica en JSON"
    )
    parser.add_argument(
        "--salida",
        required=True,
        type=pathlib.Path,
        help=f"carpeta donde se escriben {ARCHIVO_LEADS} e {ARCHIVO_INFORME}",
    )
    return parser.parse_args(argumentos)


def comprobar_export(ruta: pathlib.Path) -> None:
    """Falla antes de escribir nada si el export no se puede leer o no es JSON."""
    json.loads(ruta.read_text(encoding="utf-8"))


def escribir_salida_sin_leads(carpeta: pathlib.Path, perfil: str, entrada: pathlib.Path) -> None:
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / ARCHIVO_LEADS).write_text("", encoding="utf-8")
    informe = {"perfil": perfil, "entrada": entrada.name, "leads_normalizados": 0}
    (carpeta / ARCHIVO_INFORME).write_text(
        json.dumps(informe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
