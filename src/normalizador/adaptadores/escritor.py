"""Escribe la salida de una carga: `leads.jsonl`, `cuarentena.jsonl` e `informe.json`.

Cada archivo se escribe entero en un temporal y se renombra encima (atómico), y el informe va el
último: si existe, la carga está completa y los otros dos archivos son de la misma carga (REC-019).
"""

from __future__ import annotations

import json
import os
import pathlib
from collections.abc import Iterable
from dataclasses import asdict

from normalizador.aplicacion.pipeline import ResultadoDeCarga

ARCHIVO_LEADS = "leads.jsonl"
ARCHIVO_CUARENTENA = "cuarentena.jsonl"
ARCHIVO_INFORME = "informe.json"


class EscritorDeArchivos:
    def escribir(self, carpeta: pathlib.Path, resultado: ResultadoDeCarga) -> None:
        carpeta.mkdir(parents=True, exist_ok=True)
        _escribir(carpeta / ARCHIVO_LEADS, _jsonl(asdict(lead) for lead in resultado.leads))
        _escribir(carpeta / ARCHIVO_CUARENTENA, _jsonl(asdict(r) for r in resultado.cuarentena))
        informe = json.dumps(resultado.informe(), ensure_ascii=False, indent=2) + "\n"
        _escribir(carpeta / ARCHIVO_INFORME, informe)


def _jsonl(filas: Iterable[dict[str, object]]) -> str:
    return "".join(_json(fila) + "\n" for fila in filas)


def _json(fila: dict[str, object]) -> str:
    """UTF-8 legible. Si un texto trae un surrogate suelto (un emoji roto en el CRM), esa fila va
    con escapes ASCII: es el mismo valor en JSON y la carga no se pierde."""
    texto = json.dumps(fila, ensure_ascii=False)
    try:
        texto.encode("utf-8")
    except UnicodeEncodeError:
        return json.dumps(fila, ensure_ascii=True)
    return texto


def _escribir(ruta: pathlib.Path, texto: str) -> None:
    temporal = ruta.with_name(ruta.name + ".tmp")
    try:
        temporal.write_text(texto, encoding="utf-8")
        os.replace(temporal, ruta)
    except BaseException:
        temporal.unlink(missing_ok=True)  # nada a medias en la carpeta de salida
        raise
