"""El histórico acumulado de cargas en un archivo JSONL: una línea por carga, solo con agregados.

Vive fuera de git (`datos/historico_calidad.jsonl`); vale para una persona y pocas clínicas (con
varias personas o cargas en paralelo, base de datos: REC-004). Una misma huella de export y perfil
no se anota dos veces (REQ-NOR-030).
"""

from __future__ import annotations

import json
import pathlib
from dataclasses import asdict

from normalizador.dominio.calidad import CalidadDeCampo, CargaEnHistorico


class HistoricoIlegible(ValueError):
    """El archivo del histórico no es nuestro JSONL: se para antes de seguir, no se ignora."""

    def __init__(self, archivo: str | pathlib.Path, motivo: str) -> None:
        self.archivo = str(archivo)
        self.motivo = motivo
        super().__init__(f"{self.archivo}: {motivo}")


class HistoricoJsonl:
    def __init__(self, ruta: pathlib.Path) -> None:
        self.ruta = ruta

    def cargas(self) -> tuple[CargaEnHistorico, ...]:
        """Las cargas anotadas; antes comprueba que el histórico se podrá escribir al terminar."""
        try:
            self.ruta.parent.mkdir(parents=True, exist_ok=True)
            self.ruta.touch(exist_ok=True)
        except OSError as error:
            raise HistoricoIlegible(self.ruta, f"no se puede escribir: {error.strerror}") from error
        lineas = self.ruta.read_text(encoding="utf-8").splitlines()
        return tuple(
            _carga(self.ruta, numero, linea)
            for numero, linea in enumerate(lineas, start=1)
            if linea.strip()
        )

    def anotar(self, carga: CargaEnHistorico) -> bool:
        if any(c.perfil == carga.perfil and c.huella == carga.huella for c in self.cargas()):
            return False
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        with self.ruta.open("a", encoding="utf-8") as archivo:
            archivo.write(json.dumps(asdict(carga), ensure_ascii=False) + "\n")
        return True


def _carga(ruta: pathlib.Path, numero: int, linea: str) -> CargaEnHistorico:
    try:
        fila = json.loads(linea)
        return CargaEnHistorico(
            perfil=str(fila["perfil"]),
            huella=str(fila["huella"]),
            fecha=str(fila["fecha"]),
            registros=int(fila["registros"]),
            leads=int(fila["leads"]),
            cuarentena=int(fila["cuarentena"]),
            por_campo={
                str(campo): CalidadDeCampo(
                    con_aviso=int(calidad["con_aviso"]),
                    porcentaje=float(calidad["porcentaje"]),
                    motivos={str(k): int(v) for k, v in dict(calidad["motivos"]).items()},
                )
                for campo, calidad in dict(fila["por_campo"]).items()
            },
        )
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        motivo = f"la línea {numero} no es una carga del histórico ({type(error).__name__})"
        raise HistoricoIlegible(ruta, motivo) from error
