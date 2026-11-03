"""El extractor con Claude tras el puerto `Extractor` (ADR-0002), con el diccionario como respaldo.

Pide una salida estructurada que la API garantiza según el esquema y la vuelve a validar aquí
(catálogo, urgencia, idioma); si el modelo falla, se agota el tiempo, se niega o la salida no vale,
extrae con el diccionario y deja el aviso `extraccion_respaldo` (REQ-NOR-024). El texto del paciente
va enmascarado (REQ-NOR-026) y delimitado como dato en el mensaje de usuario, nunca en el sistema
(REQ-NOR-025). No usa el respaldo de modelo del servidor (`fallbacks`), que exige el espacio beta
del SDK: ante una negativa, el respaldo es el diccionario.
"""

from __future__ import annotations

import logging
import pathlib
import re
from dataclasses import dataclass
from typing import Literal, Protocol

import anthropic
import pydantic
import yaml

from normalizador.aplicacion.puertos import Extractor
from normalizador.dominio.avisos import Aviso, esta_ausente
from normalizador.dominio.enmascarado import ReglasDeEnmascarado, enmascarar
from normalizador.dominio.extraccion import (
    ALTA,
    BAJA,
    MEDIA,
    SIN_TEXTO,
    ExtraccionDelTexto,
    ReglasDeExtraccion,
)

logger = logging.getLogger("normalizador")

CAMPO_EXTRACCION = "extraccion"
EXTRACCION_RESPALDO = "extraccion_respaldo"
HUECO_DEL_MENSAJE = "{{entrada}}"
CODIGO_DE_IDIOMA = re.compile(r"[a-z]{2}")
CABECERA = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.DOTALL)
SECCION = re.compile(r"^## (.+?)\n(.*?)(?=^## |\Z)", re.DOTALL | re.MULTILINE)
URGENCIAS = (ALTA, MEDIA, BAJA)


class ClienteDeMensajes(Protocol):
    """Lo que el extractor usa de `anthropic.Anthropic`: `messages.parse(...)`."""

    messages: object


@dataclass(frozen=True)
class Prompt:
    """Una versión de `prompts/extraccion-lead/vN.md`, la misma que evalúa `make eval-ia`."""

    modelo: str
    esfuerzo: str
    max_tokens: int
    fallbacks: str
    estado: str
    sistema: str
    usuario: str

    @classmethod
    def desde_archivo(cls, ruta: pathlib.Path) -> Prompt:
        partes = CABECERA.match(ruta.read_text(encoding="utf-8"))
        if partes is None:
            raise ValueError(f"{ruta}: el prompt necesita una cabecera YAML entre líneas `---`.")
        cabecera = yaml.safe_load(partes.group(1)) or {}
        secciones = {
            titulo.strip(): cuerpo.strip() for titulo, cuerpo in SECCION.findall(partes.group(2))
        }
        if "Sistema" not in secciones or "Usuario" not in secciones:
            raise ValueError(f"{ruta}: faltan las secciones `## Sistema` o `## Usuario`.")
        if HUECO_DEL_MENSAJE not in secciones["Usuario"]:
            raise ValueError(f"{ruta}: `## Usuario` necesita el hueco {HUECO_DEL_MENSAJE}.")
        if "modelo" not in cabecera:
            raise ValueError(f"{ruta}: la cabecera necesita `modelo`.")
        return cls(
            modelo=str(cabecera["modelo"]),
            esfuerzo=str(cabecera.get("esfuerzo", "medium")),
            max_tokens=int(cabecera.get("max_tokens", 4000)),
            fallbacks=str(cabecera.get("fallbacks", "no")),
            estado=str(cabecera.get("estado", "borrador")),
            sistema=secciones["Sistema"],
            usuario=secciones["Usuario"],
        )

    def mensaje(self, entrada: str) -> str:
        return self.usuario.replace(HUECO_DEL_MENSAJE, entrada)


class ExtractorConClaude:
    def __init__(
        self,
        cliente: ClienteDeMensajes,
        prompt: Prompt,
        reglas: ReglasDeExtraccion,
        enmascarado: ReglasDeEnmascarado,
        respaldo: Extractor,
    ) -> None:
        self.cliente = cliente
        self.prompt = prompt
        self.reglas = reglas
        self.enmascarado = enmascarado
        self.respaldo = respaldo
        self.salida = _modelo_de_salida(tuple(reglas.especialidades))

    def extraer(self, texto: str | None) -> ExtraccionDelTexto:
        if esta_ausente(texto) or not isinstance(texto, str):
            return SIN_TEXTO
        enviado = enmascarar(texto, self.enmascarado).texto
        try:
            respuesta = self.cliente.messages.parse(
                model=self.prompt.modelo,
                max_tokens=self.prompt.max_tokens,
                output_config={"effort": self.prompt.esfuerzo},
                system=self.prompt.sistema,
                messages=[{"role": "user", "content": self.prompt.mensaje(enviado)}],
                output_format=self.salida,
            )
            return self._validar(respuesta)
        except (anthropic.AnthropicError, pydantic.ValidationError, ValueError) as error:
            datos = {"motivo": type(error).__name__}
            logger.info("extraccion con respaldo", extra={"datos": datos})
            return self._con_respaldo(texto)

    def _validar(self, respuesta: object) -> ExtraccionDelTexto:
        """La API garantiza el esquema; aquí se comprueba además el catálogo y los códigos."""
        if getattr(respuesta, "stop_reason", None) != "end_turn":
            raise ValueError(f"stop_reason {getattr(respuesta, 'stop_reason', None)!r}")
        salida = getattr(respuesta, "parsed_output", None)
        if salida is None:
            raise ValueError("sin salida estructurada")
        especialidad = salida.specialty
        if especialidad is not None and especialidad not in self.reglas.especialidades:
            raise ValueError("especialidad fuera del catálogo")
        if salida.urgency not in URGENCIAS:
            raise ValueError("urgencia fuera de alta, media o baja")
        if salida.has_reports is not None and not isinstance(salida.has_reports, bool):
            raise ValueError("has_reports tiene que ser true, false o null")
        idioma = salida.language
        es_codigo = isinstance(idioma, str) and CODIGO_DE_IDIOMA.fullmatch(idioma) is not None
        if idioma is not None and not es_codigo:
            raise ValueError("idioma sin código ISO 639-1")
        return ExtraccionDelTexto(especialidad, salida.urgency, salida.has_reports, idioma)

    def _con_respaldo(self, texto: str) -> ExtraccionDelTexto:
        del_diccionario = self.respaldo.extraer(texto)
        return ExtraccionDelTexto(
            specialty=del_diccionario.specialty,
            urgency=del_diccionario.urgency,
            has_reports=del_diccionario.has_reports,
            language=del_diccionario.language,
            avisos=del_diccionario.avisos + (Aviso(CAMPO_EXTRACCION, EXTRACCION_RESPALDO),),
        )


def _modelo_de_salida(catalogo: tuple[str, ...]) -> type[pydantic.BaseModel]:
    """El esquema de la salida: la API solo puede devolver una especialidad del catálogo."""
    return pydantic.create_model(
        "SalidaDeExtraccion",
        specialty=(Literal[catalogo] | None, ...),
        urgency=(Literal[URGENCIAS], ...),
        has_reports=(bool | None, ...),
        language=(str | None, ...),
    )
