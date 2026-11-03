# Checklist de observabilidad

Objetivo: saber que algo va mal **antes** que el cliente, y poder diagnosticarlo sin adivinar.
Tiene que estar lista antes del primer despliegue a producción, no después del primer incidente.

## Señales
- [ ] **Logs estructurados** (JSON) con `request_id`, `tenant_id`/cliente y versión; sin datos personales.
- [ ] **Métricas RED** por operación y por cliente: peticiones (*Rate*), errores (*Errors*), latencia (*Duration*, p50/p95/p99).
- [ ] **Trazas** en las llamadas externas (BD, APIs, modelo de IA) para ver dónde se va el tiempo.
- [ ] **Métrica de negocio** de la spec (la que define el éxito) medida en producción desde el día 1.

## Objetivos y alertas
- [ ] **SLO** por flujo crítico (p. ej. 99,9% de peticiones OK y p95 < 300 ms en 30 días) y su presupuesto de error.
- [ ] Alertas sobre **síntomas** (el SLO se está quemando), no sobre causas (CPU al 80%).
- [ ] Cada alerta tiene un **runbook** en `docs/runbooks/` (plantilla: `docs/plantillas/runbook.md`): qué significa,
      cómo diagnosticar, cómo mitigar, a quién escalar.

## Si hay IA en el producto
- [ ] Por petición: latencia, tokens, **coste**, errores y reintentos del modelo.
- [ ] Calidad online: % de salidas aceptadas sin edición, tasa de escalado a humano, feedback del usuario.
- [ ] Muestra periódica de salidas reales (anonimizadas) revisada por expertos → nuevos casos en `prompts/<f>/casos.jsonl`
      y notas para recalibrar el juez (`prompts/<f>/humanas.jsonl`).
- [ ] Alerta si cambia la distribución de entradas o cae la calidad (*drift*).

## Paneles
- [ ] Uno de **negocio** (métrica de éxito, adopción) y uno **técnico** (SLO, errores, coste).

## Claude Code en producción
- Solo **lectura** (logs, métricas, trazas) para diagnosticar. Los cambios vuelven a pasar por
  spec → test → PR → pipeline. Un incidente se lleva con `/incidente` y cierra con su postmortem
  (`docs/plantillas/postmortem.md`) y un test o una regla nueva (`docs/prompts.md` §8).
