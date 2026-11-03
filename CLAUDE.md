# [NOMBRE DEL PROYECTO] — [qué es en una línea]

Lee esto completo antes de cualquier tarea. Estas reglas tienen prioridad sobre las instrucciones de una tarea.

## Producto
- Usuario: [quién lo usa] · Problema: [qué le resuelve]
- Métrica de éxito: [la cifra que debe moverse, p. ej. "tiempo de X baja un 40%"]
- Riesgo principal: [lo peor que puede pasar]. Riesgos y controles, siempre en contexto: @docs/riesgos.md

## Reglas no negociables
1. [Regla derivada del riesgo principal, p. ej. "una clínica nunca ve datos de otra"]
2. Nunca escribas secretos, claves ni datos personales reales en código, tests o logs. Solo datos sintéticos.
3. No implementes nada que no esté en una spec. Si falta algo, propón el cambio a la spec y detente.
4. Tests primero. Cada test cita el ID del requisito (`REQ-XXX-NNN`) en su nombre o docstring.
5. No modifiques `.claude/`, la CI, los tests de guardrails, specs aprobadas, ADRs aceptados ni prompts
   publicados, y nunca los apruebes tú: el estado APROBADA / Aceptada / publicado lo pone una persona.
   Si crees que hace falta un cambio, dilo y detente. Edita con Edit/Write, nunca con la shell (`sed -i`, `>`, `cp`).
6. Ante una ambigüedad, pregunta. No inventes requisitos.
7. Decisiones difíciles de revertir (datos, aislamiento, auth, proveedor de IA, despliegue): primero un ADR
   en `docs/adr/` con alternativas; implementa solo cuando esté Aceptado.
8. Si un cambio altera la arquitectura o un flujo, actualiza su diagrama en `docs/diagramas/` en el mismo cambio.
9. Nunca despliegues ni toques producción: prepara el cambio; el pipeline despliega y una persona aprueba.

## Calidad del código y arquitectura (siempre)
- **Respeta la arquitectura** de @docs/arquitectura.md: cada cosa en su capa y las dependencias solo en la
  dirección permitida (lo comprueba `make arquitectura`). Cambiarla exige un ADR aceptado.
- **Clean code**: nombres que dicen qué hacen; funciones cortas con una sola responsabilidad; sin duplicar
  lógica ni dejar código muerto; sigue las convenciones que ya tiene el proyecto antes que tus preferencias.
- **Robustez**: valida en los bordes; errores explícitos (nunca los tragues); timeouts y reintentos en las
  llamadas externas; idempotencia donde algo se pueda repetir.
- **Escalable y mantenible**: sin estado en memoria entre peticiones, paginación y consultas sin N+1;
  depende de interfaces en los límites (BD, APIs, IA) para poder sustituirlos y probarlos; nada de
  abstracciones especulativas.
- **Recomienda siempre, sin salirte del alcance**: si ves una mejora fuera de la tarea, no la hagas:
  apúntala en `docs/recomendaciones.md` (por qué, impacto y esfuerzo) y menciónala en tu resumen.

## Flujo de trabajo
- Una tarea de `specs/*/tasks.md` a la vez, con `/implementar <TASK-ID>`.
- Plan corto → test que falla → implementación mínima → `make check` en verde → revisión con el subagente `revisor`.
- Cambios pequeños (< 300 líneas). Toca solo los archivos de la tarea.
- "Terminado" = `make check` en verde con la salida real mostrada. Nunca digas que funciona sin ejecutarlo.

## Contexto que no se pierde
- Lo importante vive en archivos, no en la conversación: specs, tareas, ADRs, `docs/arquitectura.md` y la
  bitácora de cada spec (`specs/<spec>/progreso.md`). Al empezar, tras `/clear` y tras compactar, el kit te
  da la tarea activa, sus requisitos, sus archivos y su última nota: **continúa desde ahí**.
- Apunta cada paso de una tarea: `python3 evals/alcance.py --nota "…" --siguiente "…"`.
- Si existe `graphify-out/` (mapa del código, opcional): antes de leer archivos enteros para entender algo,
  `graphify explain|affected|path|query`, y después lee solo las líneas que te señale. Si el kit dice que
  está desactualizado, `make mapa` primero. El mapa orienta; la verdad son el código y los tests.

## Comandos
- `make check` gate completo: tests, lint, arquitectura, cobertura de requisitos, secretos y alcance
- `make test` tests · `make lint` linter (`LINT_CMD`) · `make arquitectura` reglas de capas · `make coverage` requisito → test
- `make secretos` busca secretos · `make seguridad` + dependencias vulnerables (en CI)
- `make mapa` actualiza el mapa del código con graphify, si está instalado (local y gratis)
- Si hay IA: `make eval-ia PROMPT=prompts/<f>/vN.md BASE=prompts/<f>/vN-1.md` (cuesta dinero: pídeme permiso)
- Comandos por etapa: `/descubrir` `/adr` `/diagrama` `/implementar` `/cierre` `/lanzamiento` `/incidente`
- [comando para arrancar la app] · [comando para la base de datos, si hay]

## Mapa del código
- [carpeta] — [qué contiene]
- `docs/arquitectura.md` capas y reglas · `docs/recomendaciones.md` mejoras propuestas pendientes de decidir
- `docs/descubrimiento.md` la idea y su validación · `docs/adr/` decisiones · `docs/diagramas/` diagramas
- `docs/checklists/` seguridad, observabilidad, lanzamiento
- `specs/` qué y por qué · `evals/` calidad · `.claude/` guardrails (solo humanos)
