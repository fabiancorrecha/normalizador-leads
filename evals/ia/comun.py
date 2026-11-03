"""Piezas comunes de los evals de IA: prompts versionados, rutas, JSONL y costes.

Cada funcionalidad con IA vive en su carpeta:  prompts/<funcionalidad>/
  vN.md            versiones del prompt (cabecera con modelo y parámetros)
  casos.jsonl      casos del eval
  rubrica.md       (opcional) rúbrica propia del juez; si no, evals/ia/rubrica_juez.md
  humanas.jsonl    (opcional) notas humanas para calibrar el juez
  simulado/vN.jsonl  (opcional) salidas fijas para probar el circuito sin API
  resultados/      lo generan generar.py y juez.py
"""

import hashlib
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
RUBRICA = ROOT / "evals" / "ia" / "rubrica_juez.md"

# USD por millón de tokens: (entrada, salida, lectura de caché). Tarifa estándar de la API en 2026-10;
# revísala antes de decidir nada con el coste. Escribir en caché cuesta 1,25 veces la entrada.
PRECIOS = {
    "claude-fable-5-1": (10.0, 50.0, 0.25),
    "claude-opus-5-5": (4.0, 20.0, 0.20),
    "claude-sonnet-5-5": (2.0, 10.0, 0.20),
    # Haiku 5.5 con más de 100K tokens de entrada: 0,50 / 2,50 (lo aplica coste_usd)
    "claude-haiku-5-5": (0.10, 0.50, 0.01),
    # Destinos posibles del fallback (lectura de caché estimada al 10 % de la entrada):
    "claude-opus-5": (5.0, 25.0, 0.50),
    "claude-opus-4-8": (5.0, 25.0, 0.50),
}


def leer_jsonl(path) -> list[dict]:
    return [
        json.loads(l)
        for l in pathlib.Path(path).read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]


def escribir_jsonl(path, filas: list[dict]) -> None:
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(f, ensure_ascii=False) + "\n" for f in filas),
        encoding="utf-8",
    )


def leer_prompt(path) -> dict:
    """prompts/<funcionalidad>/vN.md → {nombre, version, sistema, usuario, modelo, ...cabecera}."""
    path = pathlib.Path(path)
    texto = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", texto, re.DOTALL)
    if not m:
        raise ValueError(
            f"{path}: falta la cabecera entre líneas --- (modelo, esfuerzo…)"
        )
    prompt = {"nombre": path.resolve().parent.name, "version": path.stem, "ruta": path}
    for linea in m.group(1).splitlines():
        if ":" in linea:
            clave, valor = linea.split(":", 1)
            prompt[clave.strip()] = valor.split("#", 1)[0].strip()
    secciones = re.split(
        r"^##\s+(Sistema|Usuario)\s*$", m.group(2), flags=re.MULTILINE | re.IGNORECASE
    )
    for titulo, cuerpo in zip(secciones[1::2], secciones[2::2]):
        prompt[titulo.lower()] = cuerpo.strip()
    for falta in ("modelo", "usuario"):
        if not prompt.get(falta):
            raise ValueError(f"{path}: falta «{falta}»")
    return prompt


def renderizar(plantilla: str, caso: dict) -> str:
    def campo(m: re.Match) -> str:
        if m.group(1) not in caso:
            raise KeyError(
                f"la plantilla usa {{{{{m.group(1)}}}}} y el caso {caso.get('id')} no lo tiene"
            )
        return str(caso[m.group(1)])

    return re.sub(r"\{\{\s*(\w+)\s*\}\}", campo, plantilla)


def es_prompt(path) -> bool:
    return bool(re.fullmatch(r"v\d+\.md", pathlib.Path(path).name))


def ruta_casos(prompt_path) -> pathlib.Path:
    return pathlib.Path(prompt_path).parent / "casos.jsonl"


def ruta_resultados(
    prompt_path, sufijo: str = "", extension: str = ".jsonl"
) -> pathlib.Path:
    p = pathlib.Path(prompt_path)
    return p.parent / "resultados" / f"{p.stem}{sufijo}{extension}"


def huella(*partes: str) -> str:
    """Identifica con qué prompt, casos y parámetros se generó un resultado (para reutilizarlo)."""
    return hashlib.sha256("\x00".join(partes).encode("utf-8")).hexdigest()[:12]


def coste_usd(
    modelo: str,
    entrada: int,
    salida: int,
    cache_escritura: int = 0,
    cache_lectura: int = 0,
):
    """Coste estimado de una llamada, o None si el modelo no está en la tabla."""
    if modelo not in PRECIOS:
        return None
    p_entrada, p_salida, p_lectura = PRECIOS[modelo]
    if (
        modelo == "claude-haiku-5-5"
        and entrada + cache_escritura + cache_lectura > 100_000
    ):
        p_entrada, p_salida, p_lectura = 0.50, 2.50, 0.05
    total = (
        entrada * p_entrada
        + cache_escritura * p_entrada * 1.25
        + cache_lectura * p_lectura
        + salida * p_salida
    )
    return round(total / 1_000_000, 6)


def percentil(valores: list[float], p: float) -> float:
    if not valores:
        return 0.0
    ordenados = sorted(valores)
    return ordenados[min(len(ordenados) - 1, round(p * (len(ordenados) - 1)))]


def relativa(path) -> str:
    try:
        return str(pathlib.Path(path).resolve().relative_to(pathlib.Path.cwd()))
    except ValueError:
        return str(path)
