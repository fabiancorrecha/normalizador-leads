---
description: Dibuja un diagrama que responde a una pregunta concreta (diagram-design o, si no está, Mermaid)
argument-hint: <qué dibujar> [para quién]
---
Diagrama de: $ARGUMENTS

1. **Pregunta**: si no está claro, pregúntame qué debe entender quién en 30 segundos. Un diagrama por
   pregunta: si salen más de 9 nodos, son dos diagramas.
2. **Tipo**: elígelo con la tabla por fase de `docs/diagramas/README.md` (recorrido, flujo, secuencia,
   estados, arquitectura, antes/después, datos, despliegue…).
3. **Herramienta**: si tienes la skill de diagram-design, úsala y guarda `docs/diagramas/<nombre>.html`. Si
   no, escríbelo en Mermaid en `docs/diagramas/<nombre>.md` (GitHub lo muestra) y dime cómo instalar
   diagram-design.
4. **Contenido**: resalta solo lo que importa (el riesgo, el cambio o el cuello de botella) y usa
   únicamente datos sintéticos.
5. **Enlace**: añádelo al documento al que sirve (spec, ADR, descubrimiento o runbook). Si contradice la
   spec o los tests, dímelo: mandan ellos, no el dibujo.
