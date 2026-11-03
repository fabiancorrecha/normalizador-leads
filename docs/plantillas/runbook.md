# Runbook — [nombre exacto de la alerta]

Servicio: [servicio] · Gravedad por defecto: [SEV] · Última revisión: [AAAA-MM-DD]
<!-- Uno por alerta, en docs/runbooks/<alerta>.md. Si una alerta no tiene runbook, no está lista
     para producción. Se escribe para alguien que lo lee a las 3 de la mañana sin contexto. -->

## Qué significa
[Qué síntoma mide la alerta y su umbral, p. ej. "el 2 % de las peticiones de /informes fallan durante 5 min".]

## Impacto para el usuario
[Qué deja de poder hacer quién. Si no afecta a nadie, sobra la alerta.]

## Diagnóstico (solo lectura)
1. Panel: [enlace] → [qué mirar primero]
2. Logs: `[consulta exacta]` → [qué buscar]
3. ¿Coincide con un despliegue? Mira el último `deploy.yml`.
4. ¿Dependencia externa (BD, proveedor de IA, cola)? [Cómo comprobarlo]

## Mitigación (de más rápida y reversible a menos)
1. Si coincide con un despliegue: vuelta atrás con el pipeline (`ROLLBACK_CMD`).
2. Si es una funcionalidad nueva: apagar su feature flag [nombre].
3. [Otras: escalar, limitar tráfico, desactivar la IA y pasar a modo manual…]

## Escalado
[Rol o equipo a avisar y cuándo: p. ej. "si en 30 min no está mitigado" o "si hay datos expuestos, ya".]

## Historial
| Fecha | Incidente | Qué cambió en este runbook |
|---|---|---|
