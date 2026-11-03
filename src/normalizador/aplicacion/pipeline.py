"""El pipeline ETL: extraer registros → mapear → normalizar → extraer del texto → validar → cargar.

Cada registro acaba en leads o en cuarentena con motivo (REQ-NOR-002 y 003). Un export que no cumple
el contrato del perfil para la carga antes de escribir nada. Los logs llevan índices, lead_id,
perfil, motivos y recuentos, nunca valores del registro (REQ-NOR-027).
"""

from __future__ import annotations

import logging
import pathlib
from collections import Counter
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from normalizador.aplicacion.puertos import (
    Escritor,
    ExportIlegible,
    Extractor,
    LectorDeExport,
    Reloj,
)
from normalizador.dominio.avisos import Aviso, esta_ausente
from normalizador.dominio.contacto import normalizar_email, normalizar_telefono
from normalizador.dominio.diccionario import Diccionario, ReglasDeLaClinica, validadores
from normalizador.dominio.extraccion import SIN_TEXTO, ExtraccionDelTexto
from normalizador.dominio.fechas import RangoPlausible, leer_fecha, normalizar_fecha
from normalizador.dominio.identidad import (
    construir_lead_id,
    copiar_texto_original,
    normalizar_nombre,
    normalizar_pais,
)
from normalizador.dominio.lead import Lead
from normalizador.dominio.mapeo import Mapeo, PerfilDeClinica, proponer_mapeo, valores_de

logger = logging.getLogger("normalizador")

REGISTRO_NO_VALIDO = "registro_no_valido"
SIN_IDENTIFICADOR = "sin_identificador"
SEPARADOR_DE_RUTA = "."


@dataclass(frozen=True)
class RegistroEnCuarentena:
    indice: int
    lead_id: str | None
    motivo: str


@dataclass(frozen=True)
class AvisoDeLead:
    lead_id: str
    indice: int
    campo: str
    codigo: str


@dataclass(frozen=True)
class ResultadoDeCarga:
    perfil: str
    entrada: str
    referencia: datetime
    registros_de_entrada: int
    mapeo: Mapeo
    leads: tuple[Lead, ...]
    cuarentena: tuple[RegistroEnCuarentena, ...]
    avisos: tuple[AvisoDeLead, ...]

    def informe(self) -> dict[str, object]:
        """El informe de la carga: recuentos, mapeo con sus candidatos y avisos; nunca valores."""
        motivos = Counter(registro.motivo for registro in self.cuarentena)
        return {
            "perfil": self.perfil,
            "entrada": self.entrada,
            "referencia": _iso_utc(self.referencia),
            "registros_de_entrada": self.registros_de_entrada,
            "leads_normalizados": len(self.leads),
            "en_cuarentena": len(self.cuarentena),
            "cuarentena_por_motivo": dict(sorted(motivos.items())),
            "mapeo": {
                campo: {
                    "ruta": mapeado.ruta,
                    "origen": mapeado.origen,
                    "aviso": mapeado.aviso,
                    "candidatos": [asdict(candidato) for candidato in mapeado.candidatos],
                }
                for campo, mapeado in self.mapeo.campos.items()
            },
            "avisos": [asdict(aviso) for aviso in self.avisos],
        }


class ExtractorNulo:
    """Un extractor que no extrae nada: para los tests del pipeline y para cargar sin extracción."""

    def extraer(self, texto: str | None) -> ExtraccionDelTexto:
        return SIN_TEXTO


class Pipeline:
    def __init__(
        self,
        diccionario: Diccionario,
        perfil: PerfilDeClinica,
        lector: LectorDeExport,
        escritor: Escritor,
        extractor: Extractor,
        reloj: Reloj,
    ) -> None:
        self.diccionario = diccionario
        self.perfil = perfil
        self.lector = lector
        self.escritor = escritor
        self.extractor = extractor
        self.reloj = reloj

    def ejecutar(self, entrada: pathlib.Path, salida: pathlib.Path) -> ResultadoDeCarga:
        export = self.lector.leer(entrada)
        registros = _registros(export, self.perfil.ruta_registros, entrada)
        reglas = self._reglas(export, entrada)
        comprobadores = validadores(reglas)
        mapeo = proponer_mapeo(
            registros, self.diccionario, comprobadores, self.perfil.mapeo_explicito
        )
        leads: list[Lead] = []
        cuarentena: list[RegistroEnCuarentena] = []
        avisos: list[AvisoDeLead] = []
        for indice, registro in enumerate(registros):
            if not isinstance(registro, Mapping):
                cuarentena.append(self._aislar(indice, REGISTRO_NO_VALIDO))
                continue
            valores, avisos_del_mapeo = valores_de(registro, mapeo, self.diccionario, comprobadores)
            identidad = construir_lead_id(self.perfil.source, valores.get("lead_id"))
            if identidad.valor is None:
                cuarentena.append(self._aislar(indice, SIN_IDENTIFICADOR))
                continue
            lead, avisos_del_lead = self._normalizar(identidad.valor, valores, reglas)
            leads.append(lead)
            avisos.extend(
                AvisoDeLead(lead.lead_id, indice, aviso.campo, aviso.codigo)
                for aviso in avisos_del_mapeo + avisos_del_lead
            )
            self._anotar_lead(lead.lead_id, indice, len(avisos_del_mapeo) + len(avisos_del_lead))
        resultado = ResultadoDeCarga(
            perfil=self.perfil.source,
            entrada=entrada.name,
            referencia=reglas.rango.referencia,
            registros_de_entrada=len(registros),
            mapeo=mapeo,
            leads=tuple(leads),
            cuarentena=tuple(cuarentena),
            avisos=tuple(avisos),
        )
        self.escritor.escribir(salida, resultado)
        recuentos = {
            "perfil": self.perfil.source,
            "registros": len(registros),
            "leads": len(leads),
            "cuarentena": len(cuarentena),
            "avisos": len(avisos),
        }
        logger.info("carga terminada", extra={"datos": recuentos})
        return resultado

    def _reglas(self, export: object, entrada: pathlib.Path) -> ReglasDeLaClinica:
        referencia = self._referencia(export, entrada)
        try:
            rango = RangoPlausible(referencia, self.perfil.antiguedad_maxima_dias)
        except ValueError as error:
            motivo = f"la fecha del export no sirve de referencia: {error}"
            raise ExportIlegible(entrada, motivo) from error
        return ReglasDeLaClinica(self.perfil.lectura, rango, self.diccionario.paises)

    def _referencia(self, export: object, entrada: pathlib.Path) -> datetime:
        """La fecha del export si el perfil la declara (obligatoria entonces); si no, el reloj."""
        if self.perfil.exportado is None:
            return self.reloj.ahora().astimezone(UTC)
        ruta = self.perfil.exportado.ruta
        lectura = self.perfil.exportado.lectura
        leida = leer_fecha(_valor_en(export, ruta), lectura, campo=ruta)
        if leida.valor is None:
            motivo = leida.avisos[0].codigo.replace("_", " ")
            raise ExportIlegible(entrada, f"la fecha del export ({ruta}): {motivo}")
        return leida.valor

    def _anotar_lead(self, lead_id: str, indice: int, avisos: int) -> None:
        datos = {
            "perfil": self.perfil.source,
            "lead_id": lead_id,
            "indice": indice,
            "avisos": avisos,
        }
        logger.info("lead normalizado", extra={"datos": datos})

    def _aislar(self, indice: int, motivo: str) -> RegistroEnCuarentena:
        datos = {"perfil": self.perfil.source, "indice": indice, "motivo": motivo}
        logger.info("registro en cuarentena", extra={"datos": datos})
        return RegistroEnCuarentena(indice, None, motivo)

    def _normalizar(
        self,
        lead_id: str,
        valores: Mapping[str, object],
        reglas: ReglasDeLaClinica,
    ) -> tuple[Lead, tuple[Aviso, ...]]:
        partes = valores.get("full_name")
        nombre = normalizar_nombre(*(partes if isinstance(partes, tuple) else (partes,)))
        email = normalizar_email(valores.get("email"))
        pais = normalizar_pais(valores.get("country"), reglas.paises)
        telefono = normalizar_telefono(valores.get("phone"), pais.valor)
        fecha = normalizar_fecha(valores.get("created_at"), reglas.lectura, reglas.rango)
        texto = copiar_texto_original(valores.get("enquiry_text"))
        # Sin texto no hay nada que extraer ni que enviar a un modelo (REQ-NOR-023).
        extraccion = SIN_TEXTO if esta_ausente(texto.valor) else self.extractor.extraer(texto.valor)
        lead = Lead(
            lead_id=lead_id,
            source=self.perfil.source,
            full_name=nombre.valor,
            email=email.valor,
            phone=telefono.valor,
            country=pais.valor,
            created_at=fecha.valor,
            enquiry_text=texto.valor,
            specialty=extraccion.specialty,
            urgency=extraccion.urgency,
            has_reports=extraccion.has_reports,
            language=extraccion.language,
        )
        avisos = (
            nombre.avisos
            + email.avisos
            + telefono.avisos
            + pais.avisos
            + fecha.avisos
            + texto.avisos
            + extraccion.avisos
        )
        return lead, avisos


def _registros(export: object, ruta: str, entrada: pathlib.Path) -> list[object]:
    contenedor = _valor_en(export, ruta) if ruta else export
    if not isinstance(contenedor, list):
        donde = f"en {ruta!r}" if ruta else "en la raíz del archivo"
        raise ExportIlegible(entrada, f"no hay una lista de registros {donde}")
    return contenedor


def _valor_en(objeto: object, ruta: str) -> object | None:
    """El valor en una ruta con puntos (`datos.exportado`), o None si algún tramo no existe."""
    for tramo in ruta.split(SEPARADOR_DE_RUTA):
        if not isinstance(objeto, Mapping) or tramo not in objeto:
            return None
        objeto = objeto[tramo]
    return objeto


def _iso_utc(instante: datetime) -> str:
    return instante.astimezone(UTC).replace(tzinfo=None).isoformat(timespec="seconds") + "Z"
