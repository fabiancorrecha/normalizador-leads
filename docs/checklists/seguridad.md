# Checklist de seguridad

Repásala al aprobar una spec que toque datos, autenticación o IA, y antes de cada lanzamiento.
La columna "Cómo se comprueba" es lo que convierte la checklist en algo verificable.

| # | Control | Cómo se comprueba |
|---|---|---|
| 1 | Ningún secreto en el código ni en el historial | Hook `guard_files.py` (agente) · `make hooks-git` (personas) · `make secretos` en CI |
| 2 | Secretos en un gestor (no en `.env` compartidos), con rotación | Revisión de la configuración del entorno |
| 3 | Dependencias auditadas y versiones fijadas (también las acciones de CI, por SHA); ninguna dependencia nueva sin justificar | `make seguridad` en CI · Dependabot con enfriamiento · revisor: "¿por qué esta dependencia?" |
| 4 | Autorización explícita en cada operación; probada también con un usuario **sin** permiso | Test por requisito: caso permitido + caso denegado |
| 5 | Entradas validadas; consultas parametrizadas; nada de `eval` ni comandos construidos con texto del usuario | Revisor + tests con entradas maliciosas |
| 6 | Datos personales: solo los necesarios, cifrados en tránsito y en reposo, con plazo de retención y borrado | Spec (requisitos) + ADR de datos |
| 7 | Logs y errores sin datos personales ni secretos: solo IDs | Regla en `.claude/hooks/reglas_proyecto.py` + test que inspecciona logs |
| 8 | **IA**: el texto de usuarios y documentos es *dato*, nunca instrucciones (*prompt injection*) | Casos trampa en `prompts/<f>/casos.jsonl` marcados como críticos (`make eval-ia`) |
| 9 | **IA**: los datos de un cliente nunca entran en el contexto de otro; nada de secretos en prompts | Test de aislamiento del contexto + revisor |
| 10 | **IA**: la salida se valida antes de usarla (formato, valores permitidos) y las acciones con efecto pasan por un humano | Tests de validación + requisito "humano en el bucle" |
| 11 | **Agente**: permisos mínimos, sin credenciales de producción en su máquina, sin modo sin permisos | `.claude/settings.json` |
| 12 | **Agente**: plugins y skills de terceros revisados antes de instalarlos (hooks, MCP, red, procesos) | Revisión como la de `docs/diagramas/README.md` |
| 13 | Modelo de amenazas ligero (STRIDE: suplantación, manipulación, repudio, fuga, denegación, escalada) en cada spec sensible | Sección "Amenazas" de la spec; para un sistema, `docs/plantillas/amenazas.md` |
| 14 | **Agente**: sandbox de Claude Code activado, para que la shell y los procesos que lanza no escriban en rutas protegidas ni salgan a la red sin permiso | Perfil de abajo · `/sandbox` |
| 15 | **Agente**: prueba de humo de los guardrails en una sesión real al empezar (`LEEME.md`) | `/hooks` + un comando bloqueado |

## Perfil endurecido: sandbox de Claude Code (opcional, recomendado)
Los hooks leen el texto de cada comando: un script que escribe archivos por su cuenta puede esquivarlos.
El sandbox lo impide a nivel de sistema operativo, también para los procesos hijos (macOS, Linux y WSL2;
en Linux necesita `bubblewrap` y `socat`; no existe en Windows nativo). Añádelo a `.claude/settings.json`
o, para probarlo solo tú, a `.claude/settings.local.json`, y compruébalo con `/sandbox`:
```json
{
  "sandbox": {
    "enabled": true,
    "allowUnsandboxedCommands": false,
    "filesystem": {
      "denyWrite": ["./.claude", "./.github/workflows", "./.github/CODEOWNERS", "./.github/dependabot.yml", "./.mcp.json",
                    "./tests/test_guardrails.py", "./tests/test_reglas_proyecto.py", "./tests/test_kit.py"],
      "denyRead": ["~/.ssh", "~/.aws", "~/.config/gcloud", "~/.kube"]
    },
    "network": {
      "allowedDomains": ["github.com", "pypi.org", "files.pythonhosted.org", "registry.npmjs.org"]
    }
  }
}
```
Ajusta `allowedDomains` a lo que tu proyecto descargue. Con `allowUnsandboxedCommands: false`, un comando
que falle dentro del sandbox no puede reintentarse fuera: más seguro, a cambio de algún bloqueo que resolverás tú.
