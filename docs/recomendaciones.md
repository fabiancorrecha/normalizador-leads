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
| REC-001 | Antes de cualquier dato real: DPA con el proveedor de IA, visto bueno del DPO al enmascarado del documento de identidad (REQ-NOR-026) y decisión sobre si `enquiry_text` debe conservarlo | Seguridad: el mensaje es un dato de salud (RGPD, art. 9) y el 4422 trae un NIE; enviarlo a un tercero sin contrato es una infracción | alto | bajo | entrevista | propuesta |
| REC-002 | Fase 2: cuarentena revisable por una persona (corregir y reprocesar de forma idempotente, con registro de quién cambió qué) | Pérdida de datos: hoy la cuarentena es un archivo que nadie está obligado a mirar; un lead en cuarentena es un paciente sin contactar | alto | medio | entrevista | propuesta |
| REC-007 | Contrato de datos por clínica: huella de la estructura del export (campos y tipos) en el perfil y aviso bloqueante si cambia | Pérdida de datos: un cambio silencioso en el CRM de una clínica (renombrar `fecha_alta`) degrada el mapeo de todas sus cargas; el reranking lo detecta como `mapeo_dudoso`, pero tarde | alto | medio | catálogo (robustez) | propuesta |
| REC-006 | Límite de tamaño del export y del texto por lead (truncar con aviso antes del LLM) y lectura en flujo para exports grandes | Seguridad y coste: un export enorme o un texto de 1 MB dispara tiempo y coste del modelo; hoy el export se carga entero en memoria | medio | bajo | catálogo (robustez) | propuesta |
| REC-003 | Fase 3: el LLM propone el perfil de una clínica nueva a partir de una muestra y una persona lo aprueba antes de usarlo | Escala: es lo que permite llegar a quince clínicas sin que cada alta dependa de alguien que conozca el diccionario (ADR-0001, opción D) | alto | medio | entrevista | propuesta |
| REC-012 | Dar cifra a la métrica de producto: tiempo de alta de una clínica nueva y % de campos que el diccionario resuelve sin mapeo explícito | Hoy la métrica de producto no tiene cifra ni plazo (spec 001, «Por qué»); sin ella no se puede decir si el SaaS mejora | medio | bajo | entrevista | propuesta |
| REC-011 | Evals del prompt de extracción en la CI (`.github/workflows/evals.yml`) con presupuesto por ejecución | Un cambio de prompt o de modelo puede romper los casos críticos (4424) sin que nadie lo note | medio | bajo | catálogo (IA) | propuesta |
| REC-013 | `mypy --strict` en `LINT_CMD` junto a ruff | Tipos en los límites: el pipeline mueve `dict` del export a dataclasses del dominio, justo donde se cuelan los errores de tipo (`id` como texto en el 4419) | medio | bajo | catálogo (clean code) | propuesta |
| REC-008 | Deducir el país del prefijo telefónico como **sugerencia** con confianza en el informe, nunca como valor del lead | 4426 (+52, Ciudad de México) sale sin país; deducirlo en silencio rompería la regla 1 | medio | bajo | entrevista | propuesta |
| REC-005 | Campo `preferred_contact_language` cuando el paciente lo dice («solo ruso», «italiano o inglés») | El comercial necesita saber en qué idioma llamar; hoy `language` es el idioma en que escribe | medio | bajo | entrevista | propuesta |
| REC-009 | Detección de idioma con una librería (`lingua-language-detector`) si el diccionario de palabras frecuentes falla en el eval | Mensajes mezclados (4424, ruso con español) e idiomas no listados | medio | bajo | entrevista | propuesta |
| REC-010 | Fase 2: deduplicación entre cargas y clínicas con una regla de negocio para fusionar | 4417 y 4420 son la misma paciente: hoy se marcan, pero el equipo puede contactarla dos veces | medio | medio | entrevista | propuesta |
| REC-004 | Fase 2: histórico de calidad en base de datos, con retención definida | El JSONL local no aguanta varias personas ni cargas en paralelo, y no tiene auditoría | medio | medio | entrevista | propuesta |
| REC-015 | Fase 2: métricas por carga (leads, cuarentena, avisos por motivo, coste y latencia del LLM) exportadas a la observabilidad (`docs/checklists/observabilidad.md`) | Hoy viven solo en el informe de cada carga; sin métricas no hay alertas | medio | medio | catálogo (operación) | propuesta |
| REC-014 | Diagramas de arquitectura y de los flujos de ADR-0001 y ADR-0002 con `/diagrama` | Regla 8 de `CLAUDE.md`; hoy solo hay el esquema en texto de `docs/arquitectura.md` | bajo | bajo | kit | propuesta |
