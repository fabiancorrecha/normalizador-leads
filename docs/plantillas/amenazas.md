# Modelo de amenazas — [sistema o funcionalidad]

Fecha: [AAAA-MM-DD] · Revisa: [rol] · Relacionado: [spec, ADR]
<!-- Para un sistema o un cambio grande. Para una sola spec basta su sección "Amenazas".
     Una hora bien usada aquí ahorra un incidente. Repásalo cuando cambie un límite de confianza. -->

## 1. Qué protegemos
| Activo | Por qué importa | Quién no debe acceder |
|---|---|---|
| [p. ej. notas clínicas] | [datos de salud: legal y confianza] | [otros clientes, personal no autorizado] |

## 2. Límites de confianza
Dónde cambia quién controla los datos: navegador → API, API → BD, API → proveedor de IA, cliente A ↔ cliente B.
Diagrama: `docs/diagramas/amenazas.html` (tipo *architecture* o *data flow*, con los límites marcados).

## 3. Amenazas (STRIDE) por límite
| Límite / componente | STRIDE | Amenaza concreta | Mitigación | Cómo se verifica |
|---|---|---|---|---|
| [API] | Suplantación | [un usuario usa el token de otro] | [tokens cortos y ligados a sesión] | [REQ-…, test] |
| | Manipulación | [cambia el id de cliente en la petición] | [el cliente sale del token, nunca de la petición] | [test con usuario sin permiso] |
| | Repudio | [nadie sabe quién borró un registro] | [registro de auditoría inmutable] | [test de auditoría] |
| | Fuga de información | [errores con datos personales] | [errores genéricos, logs solo con IDs] | [regla en reglas_proyecto.py] |
| | Denegación de servicio | [exportaciones enormes] | [límites y paginación] | [prueba de carga con umbral] |
| | Escalada de privilegios | [un rol lector llega a escribir] | [autorización en cada operación] | [test por rol] |

## 4. Si hay IA
| Amenaza | Mitigación | Cómo se verifica |
|---|---|---|
| *Prompt injection* desde el usuario o desde documentos | El texto externo es dato, nunca instrucciones; acciones con efecto pasan por una persona | Casos `critico` en `prompts/<f>/casos.jsonl` |
| Fuga entre clientes en el contexto del modelo | Contexto construido solo con datos del cliente autenticado | Test de aislamiento del contexto |
| Salida no válida o peligrosa | Salida estructurada (`esquema:`) y validada antes de usarla | Tests de validación + `campos` en los casos |
| Coste desbocado (abuso o bucles) | Límites por cliente y `max_tokens` | Alerta de coste (`docs/checklists/observabilidad.md`) |

## 5. Riesgos aceptados
[Lo que decidimos no mitigar todavía, por qué y quién lo acepta.]
