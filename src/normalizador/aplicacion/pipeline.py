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
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime

from normalizador.aplicacion.informe import bloque_de_calidad, bloque_de_historico
from normalizador.aplicacion.puertos import (
    Escritor,
    ExportIlegible,
    Extractor,
    Historico,
    LectorDeExport,
    Reloj,
)
from normalizador.dominio.avisos import Aviso, esta_ausente
from normalizador.dominio.calidad import CalidadDeCampo, CargaEnHistorico, calidad_por_campo
from normalizador.dominio.contacto import normalizar_email, normalizar_telefono
from normalizador.dominio.diccionario import Diccionario, ReglasDeLaClinica, validadores
from normalizador.dominio.extraccion import SIN_TEXTO
from normalizador.dominio.fechas import RangoPlausible, leer_fecha, normalizar_fecha
from normalizador.dominio.identidad import (
    construir_lead_id,
    copiar_texto_original,
    normalizar_nombre,
    normalizar_pais,
)
from normalizador.dominio.lead import Lead
from normalizador.dominio.mapeo import (
    MAPEO_EXPLICITO_SIN_DATOS,
    SEPARADOR_DE_RUTA,
    Mapeo,
    PerfilDeClinica,
    aplanar,
    proponer_mapeo,
    valores_de,
)

logger = logging.getLogger("normalizador")

REGISTRO_NO_VALIDO = "registro_no_valido"
SIN_IDENTIFICADOR = "sin_identificador"
IDENTIFICADOR_REPETIDO = "identificador_repetido"


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
    huella: str | None = None  # del export, el perfil, el diccionario y el extractor (REQ-NOR-030)
    rutas_del_export: tuple[str, ...] = ()
    anteriores: tuple[CargaEnHistorico, ...] = ()
    anotada: bool | None = None  # None sin histórico; False si la huella ya estaba
    extraccion: Mapping[str, object] = field(default_factory=dict)  # extractor, modelo y prompt

    def informe(self) -> dict[str, object]:
        """El informe de la carga: recuentos, mapeo, avisos, calidad e histórico; nunca valores."""
        motivos = Counter(registro.motivo for registro in self.cuarentena)
        por_campo = self.calidad_por_campo()
        rutas_mapeadas = [mapeado.ruta for mapeado in self.mapeo.campos.values()]
        return {
            "perfil": self.perfil,
            "entrada": self.entrada,
            "huella": self.huella,
            "extraccion": dict(self.extraccion),
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
            "calidad": bloque_de_calidad(
                por_campo, self.leads, self.rutas_del_export, rutas_mapeadas
            ),
            "historico": bloque_de_historico(self.perfil, por_campo, self.anteriores, self.anotada),
        }

    def calidad_por_campo(self) -> dict[str, CalidadDeCampo]:
        avisos = [(aviso.lead_id, aviso.campo, aviso.codigo) for aviso in self.avisos]
        return calidad_por_campo(len(self.leads), avisos)

    def carga_para_el_historico(self, fecha: datetime) -> CargaEnHistorico:
        """Lo que queda de esta carga en el histórico: agregados, nunca valores (REQ-NOR-029)."""
        return CargaEnHistorico(
            perfil=self.perfil,
            huella=self.huella or "",
            fecha=_iso_utc(fecha),
            registros=self.registros_de_entrada,
            leads=len(self.leads),
            cuarentena=len(self.cuarentena),
            por_campo=self.calidad_por_campo(),
        )


class Pipeline:
    def __init__(
        self,
        diccionario: Diccionario,
        perfil: PerfilDeClinica,
        lector: LectorDeExport,
        escritor: Escritor,
        extractor: Extractor,
        reloj: Reloj,
        historico: Historico | None = None,
        extraccion: Mapping[str, object] | None = None,
    ) -> None:
        self.diccionario = diccionario
        self.perfil = perfil
        self.lector = lector
        self.escritor = escritor
        self.extractor = extractor
        self.reloj = reloj
        self.historico = historico
        self.descripcion_de_la_extraccion = dict(extraccion or {})

    def ejecutar(
        self, entrada: pathlib.Path, salida: pathlib.Path, huella: str | None = None
    ) -> ResultadoDeCarga:
        export = self.lector.leer(entrada)
        registros = _registros(export, self.perfil.ruta_registros, entrada)
        anteriores = tuple(self.historico.cargas()) if self.historico is not None else ()
        anotada = self._anotada(huella, anteriores)
        reglas = self._reglas(export, entrada)
        comprobadores = validadores(reglas)
        mapeo = proponer_mapeo(
            registros, self.diccionario, comprobadores, self.perfil.mapeo_explicito
        )
        _exigir_mapeo_explicito_con_datos(mapeo, entrada)
        leads: list[Lead] = []
        cuarentena: list[RegistroEnCuarentena] = []
        avisos: list[AvisoDeLead] = []
        vistos: set[str] = set()
        for indice, registro in enumerate(registros):
            if not isinstance(registro, Mapping):
                cuarentena.append(self._aislar(indice, REGISTRO_NO_VALIDO))
                continue
            valores, avisos_del_mapeo = valores_de(registro, mapeo, self.diccionario, comprobadores)
            identidad = construir_lead_id(self.perfil.source, valores.get("lead_id"))
            if identidad.valor is None:
                cuarentena.append(self._aislar(indice, SIN_IDENTIFICADOR))
                continue
            if identidad.valor in vistos:  # el lead_id es único: el segundo no pisa al primero
                cuarentena.append(self._aislar(indice, IDENTIFICADOR_REPETIDO, identidad.valor))
                continue
            vistos.add(identidad.valor)
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
            huella=huella,
            rutas_del_export=_rutas(registros),
            anteriores=anteriores,
            anotada=anotada,
            extraccion=self.descripcion_de_la_extraccion,
        )
        self.escritor.escribir(salida, resultado)
        if anotada:  # después de escribir: una carga a medias no entra en el histórico
            self.historico.anotar(resultado.carga_para_el_historico(self.reloj.ahora()))
            datos = {"perfil": self.perfil.source, "cargas_anteriores": len(anteriores)}
            logger.info("carga anotada en el historico", extra={"datos": datos})
        recuentos = {
            "perfil": self.perfil.source,
            "registros": len(registros),
            "leads": len(leads),
            "cuarentena": len(cuarentena),
            "avisos": len(avisos),
        }
        logger.info("carga terminada", extra={"datos": recuentos})
        return resultado

    def _anotada(self, huella: str | None, anteriores: tuple[CargaEnHistorico, ...]) -> bool | None:
        """Si la carga entrará en el histórico: no sin histórico, ni si su huella ya está."""
        if self.historico is None or huella is None:
            return None
        perfil = self.perfil.source
        return not any(c.perfil == perfil and c.huella == huella for c in anteriores)

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

    def _aislar(self, indice: int, motivo: str, lead_id: str | None = None) -> RegistroEnCuarentena:
        datos = {"perfil": self.perfil.source, "indice": indice, "motivo": motivo}
        if lead_id is not None:
            datos["lead_id"] = lead_id
        logger.info("registro en cuarentena", extra={"datos": datos})
        return RegistroEnCuarentena(indice, lead_id, motivo)

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


def _exigir_mapeo_explicito_con_datos(mapeo: Mapeo, entrada: pathlib.Path) -> None:
    """Un perfil que mapea a una ruta que el export no trae es un error de contrato, no una
    columna de nulos: la carga para antes de escribir nada."""
    sin_datos = [m for m in mapeo.campos.values() if m.aviso == MAPEO_EXPLICITO_SIN_DATOS]
    if sin_datos:
        detalle = ", ".join(f"{m.campo} → {m.ruta!r}" for m in sin_datos)
        raise ExportIlegible(entrada, f"el perfil mapea a rutas que el export no trae: {detalle}")


def _registros(export: object, ruta: str, entrada: pathlib.Path) -> list[object]:
    contenedor = _valor_en(export, ruta) if ruta else export
    if not isinstance(contenedor, list):
        donde = f"en {ruta!r}" if ruta else "en la raíz del archivo"
        raise ExportIlegible(entrada, f"no hay una lista de registros {donde}")
    return contenedor


def _rutas(registros: list[object]) -> tuple[str, ...]:
    """Todas las rutas con punto que aparecen en algún registro del export."""
    objetos = (registro for registro in registros if isinstance(registro, Mapping))
    rutas = {ruta for registro in objetos for ruta in aplanar(registro)}
    return tuple(sorted(rutas))


def _valor_en(objeto: object, ruta: str) -> object | None:
    """El valor en una ruta con puntos (`datos.exportado`), o None si algún tramo no existe."""
    for tramo in ruta.split(SEPARADOR_DE_RUTA):
        if not isinstance(objeto, Mapping) or tramo not in objeto:
            return None
        objeto = objeto[tramo]
    return objeto


def _iso_utc(instante: datetime) -> str:
    return instante.astimezone(UTC).replace(tzinfo=None).isoformat(timespec="seconds") + "Z"
