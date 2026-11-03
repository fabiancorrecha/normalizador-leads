---
description: Valida una idea con evidencia antes de construirla (docs/descubrimiento.md + diagramas). No escribe código.
argument-hint: <idea en una o dos frases>
---
Ayúdame a decidir con evidencia si merece la pena construir esto: $ARGUMENTS

1. **Preguntas** (como mucho 5, de una en una si hace falta): quién lo sufre, qué hace hoy, qué
   evidencia tenemos y qué restricciones hay (plazo, presupuesto, datos sensibles). Lo que no sepamos
   se escribe como supuesto marcado; nunca inventes datos ni cifras.
2. **Documento**: rellena `docs/descubrimiento.md` (si ya describe otra idea, pregúntame si lo sustituyo o
   creo `docs/descubrimiento-<nombre>.md`): problema, hipótesis medible, los cuatro riesgos con su nivel,
   el experimento más barato para el riesgo más alto, con el criterio de éxito definido antes, y el MVP
   con lo que queda fuera.
3. **Cuestiona la idea**: qué tendría que ser verdad para que funcione y qué la mataría.
4. **Diagramas**: el recorrido actual del usuario y cómo funcionará con la solución, como en `/diagrama`.
5. **Si usa IA**: propón 10 casos sintéticos para `prompts/<funcionalidad>/casos.jsonl`. Marca como
   críticos los que nunca pueden fallar y explica qué tasa de acierto exige el valor de la idea.
6. **Recomendación**: construir, experimentar primero o descartar, y por qué. Para aquí: sin código ni
   specs hasta que yo decida.
