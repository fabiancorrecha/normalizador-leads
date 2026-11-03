# BUG-NNN — [Qué falla, en una línea]

Estado: BORRADOR · Severidad: [crítica|alta|media|baja] · Regresión: [sí, desde vX|no|no se sabe]
<!-- Cuando lo revises, cambia BORRADOR por APROBADA tú: es tu firma y el agente no puede ponerla.
     Desde ese momento el agente no puede editarlo y `make coverage` exige test para cada DEBE. -->

## Qué pasa
- **Esperado**: [comportamiento correcto]
- **Actual**: [lo que ocurre]
- **Impacto**: [a quién afecta y cuánto; ¿hay datos o seguridad en juego?]

## Cómo reproducirlo
1. [paso]
2. [paso]
- Entorno y versión: [...] · Frecuencia: [siempre|a veces|no reproducido aún]
- Evidencia: [mensaje de error o log, **sin datos personales reales**]

## Requisitos (EARS)
| ID | Requisito | Prioridad |
|----|-----------|-----------|
| REQ-BNNN-001 | CUANDO [los pasos que hoy fallan], EL SISTEMA DEBE [el comportamiento esperado]. | DEBE |
| REQ-BNNN-002 | CUANDO [una variante cercana: otro dato, otro rol, otro caso límite], EL SISTEMA DEBE [seguir funcionando]. | DEBE |

El primer test que se escribe reproduce el fallo y **falla por la razón esperada**; solo después se arregla.

## Causa raíz (se rellena al cerrar)
- Por qué pasó: [cadena de porqués hasta la causa, no el síntoma]
- Por qué no lo detectamos antes: [qué test, regla o revisión faltaba]

## Prevención
- [Test, regla de CLAUDE.md o guardrail que evita esta familia de errores (`docs/prompts.md` §8)]

## Fuera de alcance
- [Mejoras que no son el arreglo: van en otra spec]
