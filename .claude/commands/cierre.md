---
description: Resumen final honesto del trabajo, con evidencia, para cerrar la sesión o la demo
---
Prepara el cierre del trabajo de esta sesión:

1. Ejecuta `make check` y muestra la salida real. Si la tarea activa está terminada y en un commit,
   desactívala con `python3 evals/alcance.py --terminar`.
2. Resume en este orden, breve y sin adornos:
   - **Qué construimos** y por qué en ese orden (ligado al riesgo principal y a la métrica de éxito);
     apóyate en las bitácoras `specs/*/progreso.md`, no en lo que recuerdes de la conversación.
   - **Verificado**: cada afirmación con su evidencia (test, salida, eval).
   - **No verificado o supuesto**: dilo explícitamente.
   - **Riesgos abiertos** y cómo los mitigaría.
   - **Recomendaciones**: las de `docs/recomendaciones.md` todavía en "propuesta", ordenadas por impacto y
     esfuerzo, para que yo decida cuáles pasan a una spec.
   - **Siguientes pasos**: las 3 próximas tareas y la siguiente fase, con su criterio de salida.
   - **Lo que aprendimos del agente**: errores que cometió y qué regla, test o hook los evita ahora.
