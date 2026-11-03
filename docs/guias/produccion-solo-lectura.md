# Producción en solo lectura para Claude (logs, métricas, trazas)

Para diagnosticar un incidente (`/incidente`) Claude necesita ver producción. Nunca debe poder cambiarla.
**El "solo lectura" lo garantiza la credencial, no una instrucción**: si la credencial puede escribir,
tarde o temprano algo escribirá.

## Arquitectura
```
Claude Code ──(herramientas MCP de lectura)──▶ servidor MCP ──(credencial de solo lectura)──▶ logs / métricas / réplica de la BD
     │                                              └─ registra cada consulta (quién, cuándo, qué)
     └─ guard_bash.py bloquea psql/kubectl/ssh… contra producción: la única vía es el MCP
```

## Paso a paso
1. **Credencial de solo lectura**, creada para esto y con alcance mínimo:
   - Logs y métricas: una clave de API de solo lectura del proveedor de observabilidad, limitada a los
     servicios del producto.
   - Base de datos: un usuario con `GRANT SELECT` sobre una **réplica**, sin acceso a las tablas o columnas
     con datos personales (vistas enmascaradas), y con límite de tiempo por consulta.
   - Nube: un rol con permisos de lectura sobre logs y métricas, sin acceso a secretos.
2. **Servidor MCP** que use esa credencial y exponga solo herramientas de lectura. Se declara en
   `.mcp.json` (lo revisa una persona en el PR: el agente no puede editarlo) con la versión fijada y la
   credencial por variable de entorno, nunca en el archivo:
   ```json
   {
     "mcpServers": {
       "observabilidad": {
         "command": "npx",
         "args": ["-y", "<paquete-del-servidor>@<versión exacta>"],
         "env": { "API_KEY": "${OBSERVABILIDAD_SOLO_LECTURA}" }
       }
     }
   }
   ```
   Antes de instalar un servidor MCP de terceros, revísalo como cualquier dependencia: qué ejecuta, a
   qué red sale y qué hace con la credencial. En sesiones interactivas Claude Code pide aprobación para
   los servidores de `.mcp.json`, pero en `claude -p` (CI, scripts) los carga sin preguntar: el runner de
   evals del kit usa `--strict-mcp-config` para no cargar ninguno.
3. **Permisos de Claude Code**: autoriza sin preguntar solo las herramientas de lectura, una a una; el
   resto pedirá permiso.
   ```json
   { "permissions": { "allow": ["mcp__observabilidad__buscar_logs", "mcp__observabilidad__consultar_metricas"] } }
   ```
   `mcp__observabilidad__*` (todas las del servidor) solo si el servidor es de lectura por construcción.
4. **Datos personales**: lo que llega al modelo es lo que devuelve la herramienta. Que el servidor
   enmascare emails, nombres y documentos de identidad, o que solo devuelva IDs y agregados.
5. **Auditoría**: el servidor registra cada consulta. Revisa el registro en el postmortem.

## Lo que sigue prohibido
- Credenciales de producción en la máquina del desarrollador o en `.env`: el hook `guard_bash.py`
  bloquea las herramientas de infraestructura contra producción (`psql`, `kubectl`, `ssh`…).
- Cualquier cambio en producción desde la sesión. Un arreglo vuelve a pasar por bug, test, PR y
  pipeline (`/incidente` paso 5); la mitigación urgente (vuelta atrás, feature flag) la ejecuta una persona.
