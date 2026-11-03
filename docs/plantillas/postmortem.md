# Incidente AAAA-MM-DD — [síntoma en una línea]

Gravedad: [SEV1|SEV2|SEV3] · Estado: [abierto|mitigado|cerrado] · Responsable: [rol, no nombre]
<!-- Sin culpables: se analizan sistemas y decisiones, no personas. La pregunta es "qué permitió que
     pasara", nunca "quién lo hizo". Nada de datos personales: solo IDs y cifras agregadas. -->

## Resumen
[Qué pasó, a quién afectó y cómo se resolvió, en tres frases.]

## Impacto
- **Afectados**: [clientes, % de peticiones, funcionalidad] · **Duración**: [desde → hasta]
- **Datos**: [¿hubo datos expuestos o corruptos? Si sí: obligaciones legales y a quién se avisó]
- **SLO**: [presupuesto de error consumido]

## Cronología (hora local, con zona)
| Hora | Qué pasó / qué se hizo | Fuente |
|---|---|---|
| HH:MM | Primera señal: [alerta, ticket, cliente] | [enlace] |
| HH:MM | Mitigación aplicada: [qué] | |
| HH:MM | Servicio recuperado | |

## Detección
- ¿Nos enteramos **antes** que el cliente? [sí/no] · ¿Qué alerta saltó o debería haber saltado?

## Causa raíz (cinco porqués)
1. ¿Por qué falló? …
2. ¿Por qué …? …
3. …
**Causa raíz**: [la condición del sistema que lo hizo posible]

## Qué fue bien, qué fue mal y dónde tuvimos suerte
- Bien: …
- Mal: …
- Suerte: [lo que pudo ser peor y no fue por azar: también es un riesgo]

## Acciones
Cada acción es algo verificable: un test, una regla de guardrail, un caso de eval, una alerta o un runbook.
| Acción | Tipo (prevenir / detectar / mitigar) | Dónde queda | Responsable | Fecha |
|---|---|---|---|---|
| Test que reproduce el fallo | prevenir | `specs/BNNN-…/` + `tests/…` | | |
| [Alerta sobre el síntoma] | detectar | `docs/runbooks/[alerta].md` | | |
