# Recomendaciones

Mejoras que alguien vio (Claude, el revisor o una persona) y que no entraban en la tarea del momento.
Claude no las hace por su cuenta: las apunta aquí y las menciona en su resumen. **Tú decides** cuáles se
aceptan (pasan a una spec o una tarea), cuáles se aplazan y cuáles se descartan (con el motivo).

Una fila por recomendación, de más a menos prioritaria (primero seguridad y pérdida de datos; después alto
impacto con poco esfuerzo). Estado: `propuesta`, `aceptada` (con su spec o tarea), `aplazada` o
`descartada` (con el motivo). Ejemplo de fila:
`| REC-001 | Paginar el listado de pedidos | Con 10.000 pedidos la respuesta tarda segundos y crece sin límite | alto | bajo | revisor, T-004-2 | propuesta |`

| ID | Recomendación | Por qué (calidad, escala, robustez, seguridad, mantenimiento) | Impacto | Esfuerzo | Origen | Estado |
|---|---|---|---|---|---|---|
