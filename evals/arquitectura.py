#!/usr/bin/env python3
"""Arquitectura: comprueba que el código respeta las reglas de dependencia del proyecto.

Uso: arquitectura.py [--raiz DIR]

Las reglas están en un bloque ```arquitectura de docs/arquitectura.md:

    capa dominio: src/dominio/**
    capa aplicacion: src/aplicacion/**
    capa infraestructura: src/infraestructura/**, sqlalchemy, requests
    dominio no depende de: aplicacion, infraestructura
    alias @/ = src/

- Un patrón con `/` o comodines es una carpeta del proyecto; un nombre sin `/` es un paquete externo.
- Lee los imports de Python, JavaScript/TypeScript y Go (en Go, solo los del propio módulo).
- Sale con 1 si un archivo importa algo de una capa que su capa tiene prohibida, o si una línea del
  bloque no se entiende (una regla mal escrita no puede dar un verde falso). Sin reglas, avisa y pasa.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCUMENTO = pathlib.Path("docs") / "arquitectura.md"
IGNORAR = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    ".claude",
    "__pycache__",
    ".pytest_cache",
    ".kit",
    ".kit-backup",
    "graphify-out",
}
PYTHON = {".py"}
JS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
GO = {".go"}


def leer_reglas(texto: str):
    """(capas, prohibidas, alias, errores) a partir de los bloques ```arquitectura."""
    capas: dict[str, list[str]] = {}
    prohibidas: dict[str, set[str]] = {}
    alias: dict[str, str] = {}
    errores: list[str] = []
    for bloque in re.findall(r"```arquitectura[^\n]*\n(.*?)```", texto, re.DOTALL):
        for linea in bloque.splitlines():
            linea = linea.split("#", 1)[0].strip()
            if not linea:
                continue
            if m := re.fullmatch(r"capa\s+([\w-]+)\s*:\s*(.+)", linea):
                capas[m[1]] = [p.strip() for p in m[2].split(",") if p.strip()]
            elif m := re.fullmatch(r"([\w-]+)\s+no\s+depende\s+de\s*:\s*(.+)", linea):
                destinos = {p.strip() for p in m[2].split(",") if p.strip()}
                prohibidas.setdefault(m[1], set()).update(destinos)
            elif m := re.fullmatch(r"alias\s+(\S+)\s*=\s*(\S+)", linea):
                alias[m[1]] = m[2]
            else:
                errores.append(f"línea no reconocida: «{linea}»")
    for origen, destinos in prohibidas.items():
        for capa in {origen, *destinos} - set(capas):
            errores.append(
                f"la regla de «{origen}» usa la capa «{capa}», que no está definida"
            )
    return capas, prohibidas, alias, errores


def es_ruta(patron: str) -> bool:
    """Carpeta del proyecto si lleva comodines o `/` (salvo paquetes npm con ámbito, como @org/paquete)."""
    return "*" in patron or ("/" in patron and not patron.startswith("@"))


def a_regex(patron: str) -> re.Pattern:
    patron = patron.strip().removeprefix("./")
    if patron.endswith("/"):
        patron += "**"
    regex, i = "", 0
    while i < len(patron):
        if patron.startswith("/**", i) and i + 3 == len(patron):
            regex, i = regex + "(/.*)?", i + 3  # la carpeta y todo lo que contiene
        elif patron.startswith("**/", i):
            regex, i = regex + "(.*/)?", i + 3
        elif patron.startswith("**", i):
            regex, i = regex + ".*", i + 2
        elif patron[i] == "*":
            regex, i = regex + "[^/]*", i + 1
        else:
            regex, i = regex + re.escape(patron[i]), i + 1
    return re.compile(regex + r"(\.\w+)?$")


class Capas:
    def __init__(self, capas: dict[str, list[str]]):
        self.rutas = {
            n: [a_regex(p) for p in ps if es_ruta(p)] for n, ps in capas.items()
        }
        self.paquetes = {
            n: [p for p in ps if not es_ruta(p)] for n, ps in capas.items()
        }

    def de_ruta(self, ruta: str) -> set[str]:
        return {
            n
            for n, regexes in self.rutas.items()
            if any(r.match(ruta) for r in regexes)
        }

    def de_paquete(self, nombre: str) -> set[str]:
        return {
            n
            for n, paquetes in self.paquetes.items()
            for p in paquetes
            if nombre == p or nombre.startswith((p + ".", p + "/"))
        }


def fuentes(raiz: pathlib.Path):
    for carpeta, subcarpetas, archivos in os.walk(raiz):
        subcarpetas[:] = [s for s in subcarpetas if s not in IGNORAR]
        for nombre in archivos:
            ruta = pathlib.Path(carpeta) / nombre
            if ruta.suffix in PYTHON | JS | GO:
                yield ruta


def modulos_python(raiz: pathlib.Path) -> dict[str, set[str]]:
    """Nombre de módulo → rutas del proyecto (src/dominio/x.py se importa como dominio.x o src.dominio.x)."""
    indice: dict[str, set[str]] = {}
    for ruta in fuentes(raiz):
        if ruta.suffix != ".py":
            continue
        partes = list(ruta.relative_to(raiz).with_suffix("").parts)
        if partes[-1] == "__init__":
            partes.pop()
        for inicio in range(len(partes)):
            nombre = ".".join(partes[inicio:])
            if nombre:
                indice.setdefault(nombre, set()).add(ruta.relative_to(raiz).as_posix())
    return indice


def lineas_logicas(texto: str):
    """(número, línea), uniendo los imports entre paréntesis que ocupan varias líneas."""
    lineas = texto.splitlines()
    i = 0
    while i < len(lineas):
        n, linea = i + 1, lineas[i]
        if re.match(r"\s*from\s+\S+\s+import\s*\(", linea):
            while ")" not in linea and i + 1 < len(lineas):
                i += 1
                linea += " " + lineas[i].strip()
        yield n, linea
        i += 1


def imports_python(texto: str, rel: str, indice: dict[str, set[str]]):
    """(línea, lo importado, rutas del proyecto o None si es externo)."""
    paquete = pathlib.PurePosixPath(rel).parent
    for n, linea in lineas_logicas(texto):
        m = re.match(r"\s*from\s+(\.*)([\w.]*)\s+import\s+([\w*,\s()]+)", linea)
        if m and m[1]:  # relativo: se resuelve desde la carpeta del archivo
            base = paquete
            for _ in range(len(m[1]) - 1):
                base = base.parent
            nombres = [m[2]] if m[2] else [x.strip(" ()") for x in m[3].split(",")]
            for nombre in filter(None, nombres):
                destino = (base / nombre.replace(".", "/")).as_posix()
                yield n, m[1] + nombre, {destino}
            continue
        modulos = [m[2]] if m else []
        if not m and (mi := re.match(r"\s*import\s+([\w.]+(?:\s*,\s*[\w.]+)*)", linea)):
            modulos = [x.strip() for x in mi[1].split(",")]
        for modulo in modulos:
            candidatos = [
                modulo.rsplit(".", k)[0] for k in range(modulo.count(".") + 1)
            ]
            rutas = next((indice[c] for c in candidatos if c in indice), None)
            yield n, modulo, rutas


def imports_js(texto: str, rel: str, alias: dict[str, str]):
    carpeta = pathlib.PurePosixPath(rel).parent
    patron = re.compile(
        r"""(?:\bfrom\s*|\bimport\s*\(\s*|\brequire\s*\(\s*|^\s*import\s+)['"]([^'"]+)['"]"""
    )
    for n, linea in enumerate(texto.splitlines(), 1):
        for objetivo in patron.findall(linea):
            if objetivo.startswith("."):
                yield n, objetivo, {os.path.normpath((carpeta / objetivo).as_posix())}
            elif prefijo := next((a for a in alias if objetivo.startswith(a)), None):
                yield n, objetivo, {alias[prefijo] + objetivo[len(prefijo) :]}
            else:
                yield n, objetivo, None


def imports_go(texto: str, modulo: str | None):
    if not modulo:
        return
    for n, linea in enumerate(texto.splitlines(), 1):
        for objetivo in re.findall(r'^\s*(?:import\s+)?(?:[\w.]+\s+)?"([^"]+)"', linea):
            if objetivo == modulo or objetivo.startswith(modulo + "/"):
                yield n, objetivo, {objetivo[len(modulo) :].lstrip("/")}


def comprobar(raiz: pathlib.Path) -> int:
    documento = raiz / DOCUMENTO
    if not documento.exists():
        print(
            f"Arquitectura: no hay {DOCUMENTO} (recomendado: describirla y fijar sus reglas)."
        )
        return 0
    capas, prohibidas, alias, errores = leer_reglas(
        documento.read_text(encoding="utf-8")
    )
    for error in errores:
        print(f"❌ {DOCUMENTO}: {error}")
    if errores:
        return 1
    if not prohibidas:
        print(
            f"Arquitectura: sin reglas de dependencia en {DOCUMENTO} (recomendado: definirlas)."
        )
        return 0

    resolver = Capas(capas)
    indice = modulos_python(raiz)
    go_mod = raiz / "go.mod"
    modulo_go = None
    if go_mod.exists():
        m = re.search(
            r"^module\s+(\S+)", go_mod.read_text(encoding="utf-8"), re.MULTILINE
        )
        modulo_go = m[1] if m else None

    violaciones, con_archivos = [], set()
    for ruta in fuentes(raiz):
        rel = ruta.relative_to(raiz).as_posix()
        origenes = resolver.de_ruta(rel)
        con_archivos |= origenes
        vetadas = (
            set().union(*(prohibidas.get(o, set()) for o in origenes))
            if origenes
            else set()
        )
        if not vetadas:
            continue
        texto = ruta.read_text(encoding="utf-8", errors="ignore")
        if ruta.suffix in PYTHON:
            importados = imports_python(texto, rel, indice)
        elif ruta.suffix in JS:
            importados = imports_js(texto, rel, alias)
        else:
            importados = imports_go(texto, modulo_go)
        for n, objetivo, rutas in importados:
            if rutas:
                destinos = set().union(*(resolver.de_ruta(r) for r in rutas))
            else:
                destinos = resolver.de_paquete(objetivo)
            for capa in sorted(destinos & vetadas):
                origen = next(
                    o for o in sorted(origenes) if capa in prohibidas.get(o, set())
                )
                violaciones.append(
                    f"{rel}:{n} importa «{objetivo}» (capa {capa}): {origen} no depende de {capa}"
                )

    for capa in sorted(set(resolver.rutas) - con_archivos):
        if resolver.rutas[capa]:
            print(
                f"⚠ La capa «{capa}» no tiene archivos: ¿están bien escritas sus rutas?"
            )
    for v in violaciones:
        print(f"❌ {v}")
    reglas = sum(len(d) for d in prohibidas.values())
    estado = (
        "✅ se respetan" if not violaciones else f"{len(violaciones)} violación(es)"
    )
    print(
        f"Arquitectura: {len(capas)} capas, {reglas} reglas de dependencia · {estado}"
    )
    return 1 if violaciones else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--raiz", type=pathlib.Path, default=ROOT)
    return comprobar(ap.parse_args().raiz.resolve())


if __name__ == "__main__":
    sys.exit(main())
