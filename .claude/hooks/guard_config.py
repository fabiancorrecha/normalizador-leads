#!/usr/bin/env python3
"""ConfigChange: ningún cambio de configuración en plena sesión puede desactivar los guardrails.

Bloquea (exit 2) si el archivo resultante:
- activa `disableAllHooks` o pone `permissions.defaultMode` en `bypassPermissions`, o
- en `.claude/settings.json`, quita un hook del kit, su `onFailure: "block"` o `disableBypassPermissionsMode`.
Cualquier otro cambio (una regla allow nueva, el tema…) se permite.

Claude Code no muestra el bloqueo a nadie: por eso cada decisión se anota en `.kit/registro-config.log`.
Si quieres quitar un guardrail a propósito, cambia el archivo y reinicia la sesión: el bloqueo solo
protege la sesión en curso (y la CI comprueba la configuración en cada PR).
"""

import datetime
import json
import os
import pathlib
import sys

HOOKS_DEL_KIT = ("guard_bash.py", "guard_files.py", "stop_gate.py", "guard_config.py")
FALLAN_CERRADO = ("guard_bash.py", "guard_files.py", "guard_config.py")


def problemas(source: str, config: dict) -> list[str]:
    encontrados = []
    if config.get("disableAllHooks"):
        encontrados.append("activa disableAllHooks")
    permisos = config.get("permissions") or {}
    if permisos.get("defaultMode") == "bypassPermissions":
        encontrados.append("pone defaultMode en bypassPermissions")
    if source != "project_settings":
        return encontrados

    hooks = [
        h
        for grupos in (config.get("hooks") or {}).values()
        for g in grupos
        for h in g.get("hooks", [])
    ]
    for nombre in HOOKS_DEL_KIT:
        if not any(nombre in h.get("command", "") for h in hooks):
            encontrados.append(f"quita el hook {nombre}")
    for nombre in FALLAN_CERRADO:
        if any(
            nombre in h.get("command", "") and h.get("onFailure") != "block"
            for h in hooks
        ):
            encontrados.append(f"quita onFailure: block de {nombre}")
    if permisos.get("disableBypassPermissionsMode") != "disable":
        encontrados.append("quita disableBypassPermissionsMode")
    return encontrados


def registrar(linea: str) -> None:
    try:
        carpeta = (
            pathlib.Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())) / ".kit"
        )
        carpeta.mkdir(exist_ok=True)
        with open(carpeta / "registro-config.log", "a", encoding="utf-8") as f:
            f.write(
                f"{datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')} {linea}\n"
            )
    except OSError:
        pass  # el registro ayuda, pero no decide


def main() -> int:
    evento = json.load(sys.stdin)
    source = evento.get("source", "")
    archivo = evento.get("file_path", "")
    if (
        source not in ("user_settings", "project_settings", "local_settings")
        or not archivo
    ):
        return 0  # skills y políticas gestionadas: no son configuración que el kit deba vigilar
    try:
        config = json.loads(pathlib.Path(archivo).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        registrar(f"BLOQUEADO {source} {archivo}: no se puede leer como JSON ({error})")
        print(f"BLOQUEADO: {archivo} no es JSON válido.", file=sys.stderr)
        return 2
    encontrados = problemas(source, config if isinstance(config, dict) else {})
    if encontrados:
        registrar(f"BLOQUEADO {source} {archivo}: {'; '.join(encontrados)}")
        print(
            f"BLOQUEADO: el cambio en {archivo} desactiva guardrails ({'; '.join(encontrados)}).",
            file=sys.stderr,
        )
        return 2
    registrar(f"permitido {source} {archivo}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:  # noqa: BLE001 — fallo cerrado: cualquier error bloquea
        registrar(
            f"BLOQUEADO: guard_config.py ha fallado ({type(error).__name__}: {error})"
        )
        print(
            f"BLOQUEADO: el guardrail guard_config.py ha fallado ({type(error).__name__}: {error}).",
            file=sys.stderr,
        )
        sys.exit(2)
