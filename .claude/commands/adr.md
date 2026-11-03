---
description: Propone un ADR para una decisión difícil de revertir, con alternativas reales. La decisión es tuya.
argument-hint: <decisión que hay que tomar>
---
Hay que decidir: $ARGUMENTS

1. **Número y archivo**: busca el último ADR en `docs/adr/` y crea `docs/adr/NNNN-<decision-corta>.md` a
   partir de `docs/adr/0000-plantilla.md`, con `Estado: Propuesta`.
2. **Contexto**: la spec o el problema que obliga a decidir, y los riesgos de `docs/riesgos.md` que toca.
3. **Alternativas**: al menos dos reales más "aplazar la decisión". Para cada una: ventajas,
   inconvenientes, coste de revertirla y cómo encaja con los riesgos. Sin hombres de paja.
4. **Recomendación** argumentada y **cómo se verificará en el código** que se cumple: un test, una regla en
   `.claude/hooks/reglas_proyecto.py` con su test o un check de CI.
5. **Diagrama**: la arquitectura resultante o el antes y el después, en `docs/diagramas/adr-NNNN.html`
   (como en `/diagrama`).
6. **No elijas tú ni marques el ADR como Aceptado**: preséntamelo y espera. La aceptación la pongo yo (el
   hook no te deja escribirla), y desde ese momento el ADR no se edita: si cambia la decisión, va otro ADR.
