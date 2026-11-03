#!/usr/bin/env python3
"""PreToolUse(Bash): bloquea comandos peligrosos antes de ejecutarse.

Exit 2 = bloquear; el mensaje de stderr vuelve a Claude para que corrija el rumbo.
Falla cerrado: si este script revienta, también bloquea (un guardrail roto no deja pasar nada).
Es una capa de mejor esfuerzo sobre el texto del comando; la garantía a nivel de sistema operativo
la da el sandbox de Claude Code (docs/checklists/seguridad.md). Las reglas propias del proyecto
van en reglas_proyecto.py, no aquí.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
import tempfile

# Rutas que el agente no puede modificar desde la shell: se editan con Edit/Write (que comprueban
# si están aprobadas) o las cambia una persona.
PROTEGIDA = (
    r"(\.claude/|\.github/(workflows/|CODEOWNERS|dependabot\.ya?ml)|tests/test_(guardrails|reglas_proyecto|kit)\.py"
    r"|specs/[^/\s'\"]+/spec\.md|docs/adr/\d{4}-|prompts/[^/\s'\"]+/(v\d+\.md|resultados/)|\.mcp\.json|docs/arquitectura\.md)"
)
ESCRITURA_EN_PROTEGIDA = [
    rf"(>{{1,2}}|\btee\b(\s+-\S+)*)\s*[\"']?[^\s\"'|;&]*{PROTEGIDA}",  # redirección o tee hacia ella
    r"\b(sed|perl)\s+(-\S+\s+)*-[a-zA-Z]*i",  # edición in situ
    r"\b(cp|mv|rm|truncate|dd|ln|chmod|chown|patch|rsync)\b",
    r"\bgit\s+(checkout|restore|rm|mv|apply)\b",
    r"\b(python3?|node|ruby|perl|bash|sh|zsh)\s+(-[a-zA-Z]*[ce]\b|-\s*$|-?\s*<<)",  # código en línea
]

# Notas que Claude Code guarda entre sesiones (~/.claude/projects/<proyecto>/memory/): no son guardrails
# ni configuración, así que nombrarlas no cuenta como tocar una ruta protegida (ver guard_files.py).
_CASA = re.escape(os.path.expanduser("~"))
MEMORIA_DE_CLAUDE = rf"(?:~|\$HOME|\$\{{HOME\}}|{_CASA})/\.claude/projects/[^/\s'\"]+/memory(?:/[^\s'\";|&<>]*)?"

ENV_SECRETO = r"\.env(?!\.(example|sample|template|dist)\b)\b"
INFRA = (
    r"\b(psql|mysql|mongo(sh)?|redis-cli|pg_dump|pg_restore|ssh|scp|rsync|kubectl|helm|terraform"
    r"|aws|gcloud|az|fly(ctl)?|heroku|railway|ansible(-playbook)?)\b|DATABASE_URL"
)
PRODUCCION = r"(?<![a-z])(prod|production|producci[oó]n)(?![a-z])"

GENERICAS = [
    (r"\bgit\s+push\b.*(--force|\s-f\b)", "Push forzado prohibido."),
    (
        r"\bgit\s+(commit|push)\b.*--no-verify",
        "Saltarse los hooks de git está prohibido.",
    ),
    (r"\bgit\s+reset\s+--hard\s+origin", "Reset destructivo contra el remoto."),
    (
        r"\bgit\s+clean\s+-[a-z]*f",
        "Borra ficheros no versionados de forma irreversible.",
    ),
    (
        rf"^(?=.*(?:{INFRA}))(?=.*{PRODUCCION})",
        "Prohibido tocar producción desde el agente.",
    ),
    (
        (
            r"\bmake\s+(deploy|rollback)\b|\bterraform\s+(apply|destroy)\b|\bkubectl\s+(apply|delete|rollout|scale)\b"
            r"|\bhelm\s+(install|upgrade|uninstall|rollback)\b|\bvercel\b.*--prod|\bfly\s+deploy\b"
            r"|\bgcloud\s+\S+\s+deploy\b|\bgcloud\s+run\s+deploy\b|\bserverless\s+deploy\b|\baws\s+\S+\s+deploy\b"
        ),
        "Los despliegues solo los hace el pipeline con aprobación humana (docs/checklists/lanzamiento.md).",
    ),
    (
        r"\bDROP\s+(DATABASE|SCHEMA|TABLE)\b|\bTRUNCATE\s+(TABLE\s+)?[\"\w]",
        "SQL destructivo: hazlo con una migración revisada.",
    ),
    (
        (
            # en la misma línea: un heredoc que solo menciona .env en su texto no lo lee
            rf"\b(cat|less|more|head|tail|grep|egrep|awk|sed|bat|strings|xxd|od|base64|cp|mv|scp|type)\b[^|;&\n]*{ENV_SECRETO}"
            rf"|\b(python3?|node|ruby|perl)\s+-[a-zA-Z]*[ce]\b.*{ENV_SECRETO}"
        ),
        "Lectura de secretos (.env) bloqueada.",
    ),
    (
        (
            r"\bprintenv\b|(^|[;&|]\s*)(env|export\s+-p|declare\s+-x|set)\s*($|[;&|])"
            r"|secretsmanager|gcloud\s+secrets|vault\s+(read|kv\s+get)"
        ),
        "Volcado de variables o secretos bloqueado.",
    ),
    (
        (
            r"\.aws/credentials|\.ssh/id_|\.netrc\b|\.docker/config\.json|\.kube/config|\.config/gcloud|\.pypirc"
            r"|\.git-credentials|\.npmrc"
        ),
        "Acceso a credenciales locales bloqueado.",
    ),
    (r"--dangerously-skip-permissions", "No se desactivan los permisos."),
]


# graphify (mapa del código, opcional): el agente solo lo consulta o lo actualiza. Instalar sus
# integraciones (escriben en .claude/, CLAUDE.md, hooks y config de git), pasar documentos por un modelo
# (cuesta dinero) o traer otra versión con uvx/pipx (sin fijar) lo decide una persona.
GRAPHIFY_PERMITIDOS = {
    "update",
    "query",
    "path",
    "explain",
    "affected",
    "god-nodes",
    "--version",
    "--help",
    "-h",
    "help",
}
LANZADORES = {"sudo", "command", "nohup", "time", "exec", "env"}


def argumentos(command: str):
    """argv de cada comando de la línea, sin variables delante ni sudo/nohup/env…"""
    for segmento in re.split(r"&&|\|\||[;|&\n]", command):
        try:
            argv = shlex.split(segmento)
        except ValueError:
            argv = segmento.split()
        while argv and (argv[0] in LANZADORES or re.match(r"^\w+=", argv[0])):
            argv.pop(0)
        if argv:
            yield argv


def graphify_no_permitido(command: str) -> str | None:
    for argv in argumentos(command):
        nombre = os.path.basename(argv[0])
        if any(re.match(r"graphifyy\b", a) for a in argv) and nombre in (
            "pip",
            "pip3",
            "pipx",
            "uv",
            "uvx",
            "python",
            "python3",
        ):
            return (
                "Instalar o lanzar graphify con pip/uv/uvx/pipx lo decide una persona "
                "(versión fijada: `uv tool install graphifyy==<GRAPHIFY_VERSION del Makefile>`)."
            )
        if nombre.startswith("python") and argv[1:3] == ["-m", "graphify"]:
            argv = argv[2:]
            nombre = "graphify"
        if nombre == "graphify":
            sub = argv[1] if len(argv) > 1 else ""
            if sub not in GRAPHIFY_PERMITIDOS:
                return (
                    f"graphify {sub or '(sin subcomando)'}: el agente solo consulta el mapa "
                    "(explain, affected, path, query, god-nodes) o lo actualiza (`make mapa`). "
                    "Instalar integraciones o hooks, o usar un modelo con coste, lo decide una persona."
                )
    return None


# Envío de datos fuera de la máquina. Se mira cada comando de la línea por separado y distinguiendo
# mayúsculas (en curl, -F es un formulario con archivos y -f, «falla si hay error»). Enviar a la propia
# API en local (127.0.0.1, localhost) para probarla no es exfiltración.
EXFILTRACION = re.compile(
    r"\b(curl|wget|nc|ncat|scp)\b.*(\s-d\s*@|\s--data(-binary|-raw|-urlencode)?\b|\s-F\s|\s--form\b"
    r"|\s--upload-file\b|\s-T\s|\s--post-(file|data)\b)"
)
HOST_DE_URL = re.compile(r"https?://\[?([^/\s:'\"\]]+)")
LOCALES = {"localhost", "127.0.0.1", "::1"}


def exfiltracion(command: str) -> bool:
    for segmento in re.split(r"&&|\|\||[;|&\n]", command):
        if not EXFILTRACION.search(segmento):
            continue
        hosts = set(HOST_DE_URL.findall(segmento))
        sin_esquema = not hosts and re.search(
            r"(?<![\w.])(localhost|127\.0\.0\.1)(:\d+)?\b", segmento
        )
        if (hosts and hosts <= LOCALES) or sin_esquema:
            continue
        return True
    return False


def _objetivo_peligroso(objetivo: str, proyecto: str, base: str | None) -> bool:
    casa = os.path.expanduser("~")
    objetivo = re.sub(r"^\$\{?HOME\}?", casa, objetivo)
    # "./*" y "*" borran el directorio que los contiene
    objetivo = re.sub(r"(/?\*)+$", "", objetivo) or "."
    objetivo = os.path.expanduser(objetivo)
    if base is None and not os.path.isabs(objetivo):
        return True  # tras un cd que no se puede seguir (cd -, cd $(…)), no se sabe qué borraría
    ruta = os.path.realpath(os.path.join(base or proyecto, objetivo))
    temporales = {
        os.path.realpath(p) for p in (tempfile.gettempdir(), "/tmp", "/var/tmp")
    }
    if ruta == proyecto or proyecto.startswith(ruta.rstrip(os.sep) + os.sep):
        return True  # el proyecto entero o algo que lo contiene
    dentro = ruta.startswith(proyecto + os.sep) or any(
        ruta.startswith(t + os.sep) for t in temporales
    )
    return not dentro


def borrado_recursivo_peligroso(command: str, entrada: dict) -> bool:
    from raiz import (
        raiz_de_trabajo,  # aquí y no arriba: si falta, el hook falla cerrado como cualquier otro error
    )

    proyecto = raiz_de_trabajo(entrada)
    # donde se ejecuta; los cd del comando la mueven
    base = os.path.realpath(entrada.get("cwd") or proyecto)
    for segmento in re.split(r"&&|\|\||[;|&\n]", command):
        try:
            argv = shlex.split(segmento)
        except ValueError:
            argv = segmento.split()
        while argv and (
            argv[0] in ("sudo", "command", "nohup", "time", "exec")
            or "=" in argv[0]
            or (argv[0].startswith("-") and len(argv) > 1)
        ):
            argv.pop(0)
        if argv and argv[0] in ("cd", "pushd"):
            destino = argv[1] if len(argv) > 1 else "~"
            seguible = (
                base is not None and destino != "-" and not re.search(r"[$`]", destino)
            )
            base = (
                os.path.realpath(os.path.join(base, os.path.expanduser(destino)))
                if seguible
                else None
            )
            continue
        if not argv or os.path.basename(argv[0]) != "rm":
            continue
        opciones, objetivos, fin = [], [], False
        for arg in argv[1:]:
            if not fin and arg == "--":
                fin = True
            elif not fin and arg.startswith("-") and arg != "-":
                opciones.append(arg)
            else:
                objetivos.append(arg)
        recursivo = any(
            o == "--recursive" or (not o.startswith("--") and re.search("[rR]", o))
            for o in opciones
        )
        if recursivo and any(_objetivo_peligroso(o, proyecto, base) for o in objetivos):
            return True
    return False


def escribe_en_ruta_protegida(command: str) -> bool:
    # con «..» la ruta podría salir de la carpeta de notas (memory/../../settings.json): esa no se exime
    command = re.sub(
        MEMORIA_DE_CLAUDE,
        lambda m: m.group(0) if ".." in m.group(0) else "NOTA_DE_MEMORIA",
        command,
    )
    return bool(re.search(PROTEGIDA, command)) and any(
        re.search(p, command) for p in ESCRITURA_EN_PROTEGIDA
    )


def reglas_del_proyecto() -> list[tuple[str, str]]:
    try:
        import reglas_proyecto
    except ModuleNotFoundError:
        return []
    return reglas_proyecto.BASH


def main() -> int:
    entrada = json.load(sys.stdin)
    command = entrada["tool_input"]["command"]
    if borrado_recursivo_peligroso(command, entrada):
        return bloquear(
            "Borrado recursivo del proyecto o de algo fuera de él.", command
        )
    motivo = graphify_no_permitido(command)
    if motivo:
        return bloquear(motivo, command)
    if escribe_en_ruta_protegida(command):
        return bloquear(
            "Archivo protegido: no se modifica desde la shell. Usa Edit/Write "
            "(comprueban si está aprobado) o pide a una persona que lo cambie.",
            command,
        )
    if exfiltracion(command):
        return bloquear("Posible exfiltración de datos.", command)
    # un 3.er elemento (ruta) no aplica a comandos
    for pattern, reason, *_ in GENERICAS + reglas_del_proyecto():
        if re.search(pattern, command, re.IGNORECASE | re.DOTALL):
            return bloquear(reason, command)
    return 0


def bloquear(motivo: str, command: str) -> int:
    print(f"BLOQUEADO por guardrail: {motivo}\nComando: {command}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:  # noqa: BLE001 — fallo cerrado: cualquier error bloquea
        print(
            f"BLOQUEADO: el guardrail guard_bash.py ha fallado ({type(error).__name__}: {error}). "
            "Avisa a una persona; no intentes rodearlo.",
            file=sys.stderr,
        )
        sys.exit(2)
