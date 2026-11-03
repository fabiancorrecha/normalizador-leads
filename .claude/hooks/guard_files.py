#!/usr/bin/env python3
"""PreToolUse(Edit|Write|NotebookEdit): protege rutas y contenido sensible.

- El agente no puede editar sus propios guardrails, la CI, los tests de guardrails,
  specs aprobadas, ADRs aceptados ni prompts publicados; tampoco aprobar ninguno de ellos.
- Ningún archivo puede contener secretos (los marcadores como '<tu-api-key>' sí).
Falla cerrado: si este script revienta, también bloquea. Las reglas propias del proyecto
van en reglas_proyecto.py, no aquí.
"""

import json
import os
import re
import sys

RUTAS_PROTEGIDAS = [
    (r"(^|/)\.claude/", "El agente no puede modificar sus propios guardrails."),
    (
        r"(^|/)\.github/(workflows/|CODEOWNERS$|dependabot\.ya?ml$)",
        "La CI, quién revisa qué y las actualizaciones automáticas solo las cambian humanos.",
    ),
    (
        r"(^|/)tests/test_(guardrails|reglas_proyecto|kit)\.py$",
        "Los tests de los guardrails solo los cambian humanos.",
    ),
    (
        r"^\.mcp\.json$",
        "A qué servidores MCP (y con qué credenciales) se conecta el agente lo decide una persona.",
    ),
    (
        r"(^|/)prompts/[^/]+/resultados/",
        "Los resultados de los evals los escriben sus scripts (make eval-ia / eval-juez), nunca el agente a mano.",
    ),
]

# Las notas que Claude Code guarda entre sesiones (~/.claude/projects/<proyecto>/memory/, fuera del proyecto)
# no son configuración ni guardrails: protegerlas solo por estar bajo una carpeta .claude/ era un falso positivo.
# Dentro del proyecto, .claude/ sigue entero protegido, y el contenido de las notas pasa el escaneo de secretos.
MEMORIA_DE_CLAUDE = r"^(\.\./)+(.*/)?\.claude/projects/[^/]+/memory/"

# Un valor entre comillas que empieza por <, $, % o { (o dice changeme, example…) es un marcador, no un secreto.
MARCADOR = r"(?![<$%{]|x{4,}|\*{4,}|changeme|cambiar|ejemplo|example|your|tu[-_])"
SECRETOS = [
    (r"AKIA[0-9A-Z]{16}", "Clave de AWS."),
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "Clave privada."),
    (r"\bsk-[A-Za-z0-9_-]{20,}", "API key."),
    (r"\bgh[pousr]_[A-Za-z0-9]{30,}", "Token de GitHub."),
    (r"\bxox[abprs]-[A-Za-z0-9-]{10,}", "Token de Slack."),
    (
        rf"(password|passwd|secret|api_?key|token)\s*[:=]\s*['\"]{MARCADOR}[^'\"\s]{{8,}}['\"]",
        "Secreto escrito en el código.",
    ),
]

# Documentos que, una vez aprobados por una persona, son contrato: el agente ya no los edita.
# La aprobación también es cosa de personas: el agente no puede escribir el estado aprobado.
CONTRATOS = [
    (r"(^|/)specs/[^/]+/spec\.md$", r"Estado:\s*\**\s*APROBADA"),
    (r"(^|/)docs/adr/\d{4}-[^/]+\.md$", r"Estado:\s*\**\s*Aceptada"),
    (r"(^|/)prompts/[^/]+/v\d+\.md$", r"(?im)^estado:\s*publicado"),
    (r"(^|/)docs/arquitectura\.md$", r"Estado:\s*\**\s*APROBADA"),
]


def contrato_aprobado(path: str) -> bool:
    for ruta, estado in CONTRATOS:
        if re.search(ruta, path) and os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return bool(re.search(estado, f.read(600)))
    return False


def reglas_del_proyecto() -> list[tuple[str, str]]:
    try:
        import reglas_proyecto
    except ModuleNotFoundError:
        return []
    return reglas_proyecto.ARCHIVOS


def main() -> int:
    from raiz import (
        raiz_de,  # aquí y no arriba: si falta, el hook falla cerrado como cualquier otro error
    )

    entrada = json.load(sys.stdin)
    tool_input = entrada["tool_input"]
    # NotebookEdit usa notebook_path
    path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    if not path:
        return 0
    # una ruta relativa cuenta desde el cwd de Claude
    path = os.path.join(entrada.get("cwd") or os.getcwd(), path)
    rel = os.path.relpath(os.path.realpath(path), raiz_de(path, entrada)).replace(
        os.sep, "/"
    )

    for pattern, reason in RUTAS_PROTEGIDAS:
        if re.search(pattern, rel) and not re.match(MEMORIA_DE_CLAUDE, rel):
            return bloquear(f"{reason} ({rel})")
    if contrato_aprobado(path):
        return bloquear(
            f"{rel} está aprobado por una persona. Propón el cambio y detente."
        )

    text = "\n".join(
        [
            tool_input.get("content", ""),
            tool_input.get("new_string", ""),
            tool_input.get("new_source", ""),
        ]
        + [e.get("new_string", "") for e in tool_input.get("edits", [])]
    )
    for ruta, estado in CONTRATOS:
        if re.search(ruta, rel) and re.search(estado, text):
            return bloquear(
                f"Solo una persona aprueba {rel}: déjalo como borrador y pide la aprobación."
            )
    # Cada regla es (patrón, motivo) o (patrón, motivo, patrón_de_ruta) para aplicarla solo en esas rutas.
    for pattern, reason, *ruta in SECRETOS + reglas_del_proyecto():
        if ruta and not re.search(ruta[0], rel):
            continue
        if re.search(pattern, text, re.IGNORECASE):
            return bloquear(f"{reason} ({rel})")
    return 0


def bloquear(motivo: str) -> int:
    print(f"BLOQUEADO: {motivo}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:  # noqa: BLE001 — fallo cerrado: cualquier error bloquea
        print(
            f"BLOQUEADO: el guardrail guard_files.py ha fallado ({type(error).__name__}: {error}). "
            "Avisa a una persona; no intentes rodearlo.",
            file=sys.stderr,
        )
        sys.exit(2)
