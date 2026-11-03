# Descubrimiento — [Nombre de la idea]

Objetivo: decidir **con evidencia** si merece la pena construirlo, ANTES de escribir la spec.
Tiempo: horas, no semanas. Rellénalo con Claude en modo Plan (`docs/prompts.md` §0).

## 1. Problema
- **Quién lo sufre**: [segmento concreto, no "los usuarios"]
- **Qué hace hoy** (alternativa actual): [hoja de cálculo, papel, competidor, nada]
- **Por qué duele**: [coste en tiempo, dinero o riesgo] · **Evidencia**: [entrevistas, datos, tickets]

## 2. Hipótesis
> Creemos que **[solución]** para **[usuario]** conseguirá **[resultado]**.
> Lo sabremos cuando **[métrica]** pase de **[X]** a **[Y]** en **[plazo]**.

## 3. Los cuatro riesgos del producto
| Riesgo | Pregunta | Nivel | Cómo lo reducimos antes de construir |
|---|---|---|---|
| Valor | ¿Lo quieren? ¿Lo pagarían? | [alto/medio/bajo] | [entrevistas, landing, preventa] |
| Usabilidad | ¿Sabrán usarlo sin ayuda? | | [prototipo navegable con 5 usuarios] |
| Viabilidad técnica | ¿Podemos construirlo? Si usa IA: ¿es suficientemente fiable? | | [prueba técnica, eval con casos reales] |
| Negocio | ¿Encaja en lo legal, comercial y de costes? | | [revisión legal, coste por uso] |

## 4. Cómo funcionará (diagramas)
- **Hoy**: recorrido actual del usuario → `docs/diagramas/recorrido-actual.html`
- **Con la solución**: cómo funcionará → `docs/diagramas/como-funcionara.html`
Generados con diagram-design (`docs/diagramas/README.md`). Un diagrama que no se entiende en
30 segundos es una idea que aún no está clara.

## 5. Experimento más barato
| Experimento | Riesgo que reduce | Coste | Criterio de éxito (definido ANTES) |
|---|---|---|---|
| [p. ej. prototipo navegable] | Usabilidad | [1 día] | [4 de 5 usuarios completan la tarea] |

**Si la idea usa IA**: antes de construir producto, junta 20-50 casos reales (anonimizados), escribe
los checks en `prompts/<funcionalidad>/casos.jsonl` y mide con `make eval-ia` (`prompts/README.md`). Si la tasa de acierto no alcanza lo que el valor exige,
la idea cambia (más humano en el bucle, alcance menor) o se para.

## 6. Alcance mínimo (MVP)
- **Dentro**: [lo mínimo que prueba la hipótesis]
- **Fuera**: [todo lo demás, explícito]

## 7. Decisión
- [ ] **Seguir** → `specs/001-[nombre]/spec.md` · [ ] **Pivotar** → [qué cambia] · [ ] **Parar**
- Motivo: [...] · Decide: [rol] · Fecha: [...]
