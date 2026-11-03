---
description: Guía un incidente de producción con diagnóstico de solo lectura, mitigación propuesta, postmortem y prevención
argument-hint: <síntoma observado>
---
Hay un incidente: $ARGUMENTS

Reglas durante todo el incidente: en producción solo **lees** (logs, métricas, trazas). Nunca cambias
producción ni despliegas: propones, y una persona ejecuta. Nada de datos personales en lo que escribas.

1. **Registro**: crea `docs/incidentes/AAAA-MM-DD-<sintoma>.md` desde `docs/plantillas/postmortem.md` y
   ve anotando la cronología con horas desde el primer minuto.
2. **Impacto**: a quién afecta, desde cuándo y con qué gravedad (SEV1-3). Si es SEV1 o puede haber datos
   expuestos, dime ya a quién hay que avisar.
3. **Diagnóstico**: si la alerta tiene runbook en `docs/runbooks/`, síguelo. Si no, hipótesis ordenadas por
   probabilidad, cada una con la consulta de solo lectura que la confirma o la descarta.
4. **Mitigación**: propón la más rápida y reversible (vuelta atrás con el pipeline, apagar el feature flag,
   escalar) y espera: la ejecuto yo.
5. **Arreglo**: con el incidente mitigado, causa raíz con cinco porqués y sin culpables. El arreglo es un bug:
   `specs/BNNN-<nombre>/` desde `specs/_plantilla/bug.md`, con el test que reproduce el fallo, y después
   `/implementar T-BNNN-1`.
6. **Prevención**: qué test, regla de guardrail (en `reglas_proyecto.py`, con su test), caso de eval, alerta
   o runbook lo habría evitado o detectado antes. Propónlo como en `docs/prompts.md` §8, sin aplicarlo
   hasta que yo lo vea, y termina el postmortem con sus acciones.
