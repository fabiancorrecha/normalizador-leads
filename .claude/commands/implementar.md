---
description: Implementa UNA tarea de specs/*/tasks.md con el flujo spec → test → código → verificación → revisión
argument-hint: <TASK-ID>
---
Implementa la tarea $ARGUMENTS siguiendo estrictamente este flujo:

1. **Contexto**: localiza $ARGUMENTS en `specs/*/tasks.md` (si el ID aparece en varias specs, pregunta
   cuál); lee su `spec.md` y `docs/riesgos.md`. Si es un bug, el primer test reproduce el fallo.
   Enumera los IDs de requisito y los archivos permitidos. Si algo es ambiguo, PARA y pregunta.
   Si la tarea cambia la arquitectura y no hay un ADR Aceptado en `docs/adr/` que la respalde, PARA y dilo.
   Activa la tarea: `python3 evals/alcance.py --iniciar $ARGUMENTS`. Desde ahí, el gate falla si tocas
   archivos fuera de los permitidos: si de verdad hace falta otro archivo, PARA y pídelo.
   Si la tarea ya estaba empezada, lee su bitácora (`specs/<spec>/progreso.md`) y sigue desde la última nota.
   Si hay mapa del código (`graphify-out/`), mira antes qué depende de lo que vas a tocar
   (`graphify affected "<símbolo>"`): son los tests y las llamadas que tu cambio puede romper.
   **Bitácora**: al cerrar cada paso de este flujo, apúntalo en una línea:
   `python3 evals/alcance.py --nota "<qué pasó o qué decidiste>" --siguiente "<próximo paso>"`. Es lo que
   te devuelve el contexto tras `/clear`, una compactación o una sesión nueva.
2. **Plan**: propón un plan de 3 a 6 pasos y espera mi aprobación.
3. **Tests primero**: escribe los tests que citan cada `REQ-XXX-NNN`. Ejecútalos y enséñame que
   FALLAN por la razón esperada.
4. **Implementación mínima**, solo en los archivos permitidos, en la capa que le corresponde según
   `docs/arquitectura.md` y con el estilo del código que la rodea. Mínima no es descuidada: nombres claros,
   errores manejados y nada duplicado.
5. **Verificación**: `make check` en verde. Pega la salida real; no la resumas. Si usas el mapa del
   código, actualízalo con `make mapa`.
6. **Revisión**: usa el subagente `revisor` sobre el diff y corrige lo CRÍTICO y ALTO.
7. **Cierre de la tarea**: con `make check` en verde, márcala como terminada en su `tasks.md` (columna
   Estado: ⏳ → ✅); así el contexto de inicio de sesión, `/kit` y `alcance.py --solapes` ya no la ofrecen
   como pendiente. Después, el **resumen**: requisitos cubiertos, archivos tocados, qué no está verificado,
   riesgos pendientes y
   **recomendaciones**: las mejoras que viste fuera del alcance (tuyas y del revisor), apuntadas en
   `docs/recomendaciones.md` con su porqué, impacto y esfuerzo. Última nota de la bitácora:
   `--nota "terminada: …" --siguiente "<la siguiente tarea>"`. No hagas commit ni push sin confirmación.
