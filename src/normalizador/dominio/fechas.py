"""Fechas de alta: los formatos que declara cada clínica, su zona horaria y un rango plausible.

Nunca se adivina (REQ-NOR-004): si un valor no encaja en ningún formato del perfil, o admite dos
lecturas (03/04/2026 con dd/mm y mm/dd, o una hora que se repite al cambiar la hora), la fecha queda
en None con su aviso. Una configuración mala no es un dato malo: falla al crearla (REQ-NOR-018).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from normalizador.dominio.avisos import Normalizado, esta_ausente

CAMPO = "created_at"
FECHA_NO_RECONOCIDA = "fecha_no_reconocida"
FECHA_AMBIGUA = "fecha_ambigua"
FECHA_FUERA_DE_RANGO = "fecha_fuera_de_rango"

ISO_8601 = "iso8601"
EPOCH_EN_SEGUNDOS = "epoch_s"
# Directivas de strptime sin zona; %b es el mes según `meses` y %p usa AM/PM (locale C).
DIRECTIVAS_ADMITIDAS = frozenset("dmYyHIpMSfb%")
DIRECTIVAS_DE_HORA = frozenset("HIpMSf")
DIRECTIVA = re.compile(r"%(.?)")
PALABRA = re.compile(r"[^\W\d_]+")


@dataclass(frozen=True)
class LecturaDeFechas:
    """Cómo escribe las fechas una clínica (sale de su perfil).

    Los formatos de `strptime` describen fechas sin zona, que se leen en `zona`; las fechas
    con desfase se declaran con `iso8601` y los epoch en segundos con `epoch_s`. `%b` es el
    nombre del mes según `meses`, no según el locale.
    """

    formatos: Sequence[str]
    zona: ZoneInfo
    meses: Mapping[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.formatos, str):
            raise ValueError("Los formatos de fecha son una lista, no un texto.")
        try:
            formatos = tuple(self.formatos)
        except TypeError as error:
            raise ValueError(f"Los formatos de fecha son una lista: {self.formatos!r}.") from error
        if not formatos:
            raise ValueError("Hace falta al menos un formato de fecha.")
        if not isinstance(self.zona, ZoneInfo):
            raise ValueError(f"La zona horaria tiene que ser una ZoneInfo, no {self.zona!r}.")
        for formato in formatos:
            _validar_formato(formato)
        meses = _meses_validados(self.meses)
        if not meses and any("%b" in formato for formato in formatos):
            raise ValueError("Un formato con %b necesita los nombres de los meses.")
        object.__setattr__(self, "formatos", formatos)
        object.__setattr__(self, "meses", meses)


@dataclass(frozen=True)
class RangoPlausible:
    """Una fecha posterior a `referencia` (la fecha del export o el reloj inyectado), o anterior en
    más de `dias_maximos` días de calendario de la clínica, no es plausible (REQ-NOR-006)."""

    referencia: datetime
    dias_maximos: int

    def __post_init__(self) -> None:
        if not isinstance(self.referencia, datetime) or self.referencia.tzinfo is None:
            raise ValueError("La referencia de las fechas es una fecha y hora con zona horaria.")
        if isinstance(self.dias_maximos, bool) or not isinstance(self.dias_maximos, int):
            raise ValueError("La antigüedad máxima es un número entero de días.")
        if self.dias_maximos <= 0:
            raise ValueError("La antigüedad máxima tiene que ser de al menos un día.")
        try:  # dos días de margen cubren el cambio de zona y el desfase al comparar
            _ = self.referencia - timedelta(days=self.dias_maximos + 2)
            _ = self.referencia + timedelta(days=2)
        except OverflowError as error:
            raise ValueError(
                "La referencia y la antigüedad máxima se salen del calendario."
            ) from error

    def admite(self, instante: datetime, zona: ZoneInfo) -> bool:
        primer_dia = self.referencia.astimezone(zona).date() - timedelta(days=self.dias_maximos)
        return _comienzo_del_dia(primer_dia, zona) <= instante <= self.referencia


def leer_fecha(
    valor: object, lectura: LecturaDeFechas, campo: str = CAMPO
) -> Normalizado[datetime]:
    """El instante (en UTC) que representa `valor`, sin mirar el rango.

    También lee la fecha del export. Como validador de contenido al mapear hay que exigir además
    el rango plausible a los enteros: con `epoch_s` declarado, cualquier id sería una fecha (el
    4417 sería un instante de 1970).
    """
    if esta_ausente(valor):
        return Normalizado.ausente(campo)
    instantes: set[datetime] = set()
    for formato in lectura.formatos:
        instantes |= _instantes(valor, formato, lectura)
    if not instantes:
        return Normalizado.con_aviso(campo, FECHA_NO_RECONOCIDA)
    if len(instantes) > 1:
        return Normalizado.con_aviso(campo, FECHA_AMBIGUA)
    return Normalizado(instantes.pop())


def normalizar_fecha(
    valor: object, lectura: LecturaDeFechas, rango: RangoPlausible
) -> Normalizado[str]:
    """ISO 8601 en UTC; una fecha fuera del rango se conserva con su aviso."""
    leida = leer_fecha(valor, lectura)
    if leida.valor is None:
        return Normalizado(None, leida.avisos)
    texto = leida.valor.replace(tzinfo=None).isoformat(timespec="seconds") + "Z"
    if not rango.admite(leida.valor, lectura.zona):
        return Normalizado.con_aviso(CAMPO, FECHA_FUERA_DE_RANGO, texto)
    return Normalizado(texto)


def _instantes(valor: object, formato: str, lectura: LecturaDeFechas) -> set[datetime]:
    """Los instantes en UTC que puede representar `valor` según `formato`; ninguno si no encaja."""
    try:
        if formato == EPOCH_EN_SEGUNDOS:
            return _desde_epoch(valor)
        if not isinstance(valor, str):
            return set()
        if formato == ISO_8601:
            return _desde_iso(valor.strip(), lectura.zona)
        return _desde_formato(valor.strip(), formato, lectura)
    except (ValueError, OverflowError, OSError):  # no encaja, o cae fuera del calendario
        return set()


def _desde_epoch(valor: object) -> set[datetime]:
    if isinstance(valor, bool) or not isinstance(valor, int | str):
        return set()
    if isinstance(valor, str) and not valor.strip().isdigit():
        return set()
    return {datetime.fromtimestamp(int(valor), tz=UTC)}


def _desde_iso(texto: str, zona: ZoneInfo) -> set[datetime]:
    if (dia := _dia_iso(texto)) is not None:
        return {_comienzo_del_dia(dia, zona)}
    fecha = datetime.fromisoformat(texto)
    if fecha.tzinfo is not None:
        return {fecha.astimezone(UTC)}
    return _lecturas_locales(fecha, zona)


def _dia_iso(texto: str) -> date | None:
    """La fecha si el texto es solo una fecha ISO (sin hora); None si trae hora o no es ISO."""
    try:
        return date.fromisoformat(texto)
    except ValueError:
        return None


def _desde_formato(texto: str, formato: str, lectura: LecturaDeFechas) -> set[datetime]:
    if "%b" in formato:
        con_numero = _mes_en_numero(texto, lectura.meses)
        if con_numero is None:
            return set()
        texto, formato = con_numero, formato.replace("%b", "%m", 1)
    local = datetime.strptime(texto, formato).replace(tzinfo=lectura.zona)
    if _sin_hora(formato):
        return {_comienzo_del_dia(local.date(), lectura.zona)}
    return _lecturas_locales(local, lectura.zona)


def _sin_hora(formato: str) -> bool:
    return not (set(DIRECTIVA.findall(formato)) & DIRECTIVAS_DE_HORA)


def _mes_en_numero(texto: str, meses: Mapping[str, int]) -> str | None:
    """Cambia el nombre del mes por su número; None si no hay exactamente un nombre de mes."""
    nombres = [
        palabra for palabra in PALABRA.finditer(texto) if palabra.group().casefold() in meses
    ]
    if len(nombres) != 1:
        return None
    nombre = nombres[0]
    numero = meses[nombre.group().casefold()]
    return f"{texto[: nombre.start()]}{numero:02d}{texto[nombre.end() :]}"


def _comienzo_del_dia(dia: date, zona: ZoneInfo) -> datetime:
    """El primer instante del día en la zona, en UTC: una fecha sin hora tiene una sola lectura
    aunque la medianoche se repita o no exista al cambiar el reloj."""
    return datetime.combine(dia, time(), tzinfo=zona).astimezone(UTC)


def _lecturas_locales(fecha: datetime, zona: ZoneInfo) -> set[datetime]:
    """Las lecturas en UTC de una hora local explícita: dos si se repite al atrasar el reloj y
    ninguna si no existe al adelantarlo. Nunca se elige una por su cuenta."""
    pared = fecha.replace(tzinfo=None)
    lecturas = {pared.replace(tzinfo=zona, fold=pliegue).astimezone(UTC) for pliegue in (0, 1)}
    return {
        lectura for lectura in lecturas if lectura.astimezone(zona).replace(tzinfo=None) == pared
    }


def _validar_formato(formato: object) -> None:
    if not isinstance(formato, str):
        raise ValueError(f"Formato de fecha no válido: {formato!r}.")
    if formato in (ISO_8601, EPOCH_EN_SEGUNDOS):
        return
    directivas = [directiva for directiva in DIRECTIVA.findall(formato) if directiva != "%"]
    if not directivas:
        raise ValueError(f"El formato de fecha {formato!r} no tiene ninguna directiva.")
    no_admitidas = sorted(
        {directiva for directiva in directivas if directiva not in DIRECTIVAS_ADMITIDAS}
    )
    if no_admitidas:
        raise ValueError(
            f"El formato de fecha {formato!r} usa directivas no admitidas {no_admitidas}: "
            f"las fechas con desfase se declaran como {ISO_8601!r} y los epoch como "
            f"{EPOCH_EN_SEGUNDOS!r}."
        )
    repetidas = sorted({directiva for directiva in directivas if directivas.count(directiva) > 1})
    if repetidas:
        raise ValueError(f"El formato de fecha {formato!r} repite las directivas {repetidas}.")
    presentes = set(directivas)
    completo = (
        len(presentes & {"Y", "y"}) == 1 and len(presentes & {"m", "b"}) == 1 and "d" in presentes
    )
    if not completo:
        raise ValueError(
            f"El formato de fecha {formato!r} necesita exactamente un año, un mes y un día."
        )
    if ("I" in presentes) != ("p" in presentes):
        raise ValueError(
            f"En el formato de fecha {formato!r}, %I (hora de 12) y %p (AM/PM) van juntos."
        )


def _meses_validados(meses: Mapping[str, int]) -> dict[str, int]:
    """Nombres de mes en minúsculas → 1-12. Falla si un nombre no es una palabra, si un número no es
    un mes o si dos nombres coinciden al ignorar mayúsculas."""
    validados: dict[str, int] = {}
    for nombre, numero in meses.items():
        if not isinstance(nombre, str) or not PALABRA.fullmatch(nombre):
            raise ValueError(f"Nombre de mes no válido: {nombre!r}.")
        if isinstance(numero, bool) or not isinstance(numero, int) or not 1 <= numero <= 12:
            raise ValueError(f"El mes {nombre!r} tiene un número fuera de 1-12: {numero!r}.")
        if nombre.casefold() in validados:
            raise ValueError(f"El nombre de mes {nombre!r} está repetido.")
        validados[nombre.casefold()] = numero
    return validados
