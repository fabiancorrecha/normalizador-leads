---
description: Prepara el lanzamiento de una spec con evidencia para cada punto de las checklists. No despliega.
argument-hint: <spec, p. ej. 003-exportar-informes>
---
Prepara el lanzamiento de: $ARGUMENTS

1. **Lee** la spec y sus tareas, sus ADRs, `docs/riesgos.md` y las tres checklists de `docs/checklists/`.
2. **Ejecuta** `make check` y pega la salida real.
3. **Recorre** `lanzamiento.md`, `seguridad.md` y `observabilidad.md` punto por punto: ✅ hecho, con la
   evidencia (archivo, test o salida); ⏳ pendiente, con lo que falta; o "no aplica", con el motivo.
   Nunca marques ✅ sin evidencia.
4. **Comprueba en el código** lo que se puede comprobar: migraciones *expand/contract* (nada se borra ni
   se renombra en el mismo paso), feature flag apagado por defecto, `ROLLBACK_CMD` definido en
   `proyecto.mk`, un runbook en `docs/runbooks/` por cada alerta nueva (`docs/plantillas/runbook.md`) y el
   modelo de amenazas si la spec toca datos, autenticación o IA (`docs/plantillas/amenazas.md`).
5. **Si hay IA**: el último `make eval-ia` de la versión de prompt que se publica está APTO, el juez está
   calibrado y el coste por petición encaja en el presupuesto.
6. **Escribe** el resultado en `docs/lanzamientos/<spec>.md` y termina con una línea: "listo para lanzar"
   solo si no queda ningún pendiente bloqueante; si no, "no listo", con la lista de lo que falta.
7. **No despliegues**: despliega `deploy.yml` y una persona lo aprueba.
