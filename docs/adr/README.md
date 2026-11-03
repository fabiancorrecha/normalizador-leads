# Registro de decisiones de arquitectura (ADR)

Un ADR deja por escrito **qué** se decidió, **qué alternativas** había y **por qué**. Seis meses
después (o en la entrevista) nadie tiene que adivinar por qué el sistema es como es.

## Cuándo escribir uno
Para decisiones **difíciles de revertir**: modelo de datos y base de datos, cómo se aíslan los clientes,
autenticación, síncrono vs. asíncrono, proveedor o modelo de IA, monolito vs. servicios, dónde se despliega.
No hace falta para decisiones baratas de cambiar (nombres, librerías pequeñas).

## Flujo con Claude Code
1. En modo Plan, Claude propone el ADR con al menos dos alternativas reales (`docs/prompts.md` §10).
2. **Tú** eliges y cambias `Estado: Propuesta` → `Aceptada`. Desde ahí el agente no puede editarlo.
3. Un ADR aceptado no se edita: si la decisión cambia, se escribe uno nuevo que lo **reemplaza**.
4. Si la decisión cambia la arquitectura, su diagrama va en `docs/diagramas/adr-NNNN.html`
   (tipo *architecture* o *architecture delta* de diagram-design).

Numeración: `0001-usamos-x-para-y.md`, `0002-...`. Plantilla: `0000-plantilla.md`.
