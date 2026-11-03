# SPEC-NNN — [Título]

Estado: BORRADOR · Fase: [N] · Aprueban: [Producto, Técnico, Seguridad…]
<!-- Cuando la revises, cambia BORRADOR por APROBADA tú (no el agente). Desde ese momento
     es un contrato: el agente no puede editarla y `make coverage` exige test para cada DEBE. -->


## Por qué
[Problema del usuario, para quién, y la métrica de negocio que mueve]

## Supuestos
- [Lo que das por hecho porque nadie te lo dijo. Dilo en voz alta y escríbelo aquí.]

## Requisitos (formato EARS: CUANDO … EL SISTEMA DEBE …)
| ID | Requisito | Prioridad |
|----|-----------|-----------|
| REQ-XXX-001 | CUANDO [disparador], EL SISTEMA DEBE [respuesta observable y testeable]. | DEBE |
| REQ-XXX-002 | CUANDO [caso de error o abuso], EL SISTEMA DEBE [comportamiento seguro]. | DEBE |
| REQ-XXX-003 | EL SISTEMA DEBERÍA [mejora deseable, no bloquea]. | DEBERÍA |

Regla: al menos un requisito DEBE cubre el riesgo principal de `docs/riesgos.md`.

## Amenazas (si toca datos, autenticación o IA; si no, borra esta sección)
| STRIDE | Amenaza concreta en esta spec | Mitigación (requisito o control) |
|---|---|---|
| Suplantación | [p. ej. alguien usa la sesión de otro] | [REQ-XXX-00N] |
| Manipulación | | |
| Repudio | | |
| Fuga de información | | |
| Denegación de servicio | | |
| Escalada de privilegios | | |
Para un sistema completo: `docs/plantillas/amenazas.md`.

## Fuera de alcance
- [Lo que NO se hace en esta spec. Es lo que más evita que el agente se desborde.]

## Criterios de aceptación
- 100% de requisitos DEBE con al menos un test (`make coverage`).
- `make check` en verde. Revisión del subagente `revisor` sin hallazgos críticos.

## Preguntas abiertas
- [Si el agente encuentra una sin resolver, se detiene y pregunta.]
