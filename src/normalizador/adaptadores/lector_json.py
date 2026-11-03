"""Lee el export de una clínica en JSON. Lo carga entero en memoria (exports grandes: REC-006)."""

from __future__ import annotations

import json
import pathlib

from normalizador.aplicacion.puertos import ExportIlegible


class LectorJson:
    def leer(self, ruta: pathlib.Path) -> object:
        try:
            texto = ruta.read_text(encoding="utf-8")
        except OSError as error:
            raise ExportIlegible(ruta, f"no se puede leer: {error.strerror}") from error
        except UnicodeDecodeError as error:
            raise ExportIlegible(ruta, "no es UTF-8") from error
        try:
            return json.loads(texto)
        except json.JSONDecodeError as error:
            motivo = f"no es JSON: {error.msg} (línea {error.lineno}, columna {error.colno})"
            raise ExportIlegible(ruta, motivo) from error
