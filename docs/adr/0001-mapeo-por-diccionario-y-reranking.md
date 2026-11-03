# ADR-0001 — Mapeamos cada clínica al esquema común con un diccionario semántico y un reranking determinista

Estado: Aceptada · Fecha: 2026-11-03 · Decide: Producto y Técnico
<!-- Cambia Propuesta por Aceptada tú (no el agente). Si más adelante cambia: "Reemplazada por ADR-NNNN". -->

## Contexto
Cada clínica exporta sus leads con otros nombres de campo (`mail`, `contacto.email`), otra estructura (lista
en la raíz o dentro de `registros`, contacto como objeto o como texto) y otros formatos. Hoy cada clínica
cuesta un script a medida y el objetivo es que entre **solo con configuración** (REQ-NOR-016, REQ-NOR-017).

Fuerzas en juego:
- **Riesgo principal** (`docs/riesgos.md`): un lead mal normalizado en silencio. Un mapeo equivocado
  corrompe todos los leads de una clínica a la vez, así que el mapeo tiene que ser explicable y, si duda,
  decirlo (REQ-NOR-014).
- **Escala**: el plan es llegar a quince clínicas; escribir a mano un mapeo completo por clínica sigue
  siendo trabajo a medida, aunque sea en YAML.
- **Datos de salud**: los valores de los campos son datos personales; el mapeo no debería necesitar
  enviarlos a terceros.
- **Coste y plazo**: fase 1 sin servicios externos para el mapeo.

## Opciones consideradas
| Opción | A favor | En contra | Coste y reversibilidad |
|---|---|---|---|
| A. Diccionario semántico (sinónimos por campo, composiciones, validadores) + reranking determinista por nombre y contenido, con umbral y margen; el perfil de la clínica puede fijar un mapeo explícito | Una clínica nueva suele entrar sin escribir nada; cada sinónimo nuevo sirve para todas las clínicas; explicable (puntuación por candidato); gratis, sin red y testeable; los valores nunca salen | El diccionario hay que mantenerlo; nombres opacos (`campo_7`) dependen del contenido; los pesos hay que calibrarlos | Bajo. Reversible: el resultado es un mapeo que se puede fijar en el perfil |
| B. Mapeo declarativo escrito a mano por clínica (YAML) | Simple y totalmente determinista | Cada clínica sigue costando trabajo manual; no aprende de una clínica a la siguiente; no da el flag de inconsistencias por campo | Bajo, pero el coste crece lineal con las clínicas |
| C. Embeddings de los nombres + modelo de reranking | Cubre sinónimos que no están en el diccionario | Coste, latencia, dependencia de un modelo y resultados menos reproducibles; difícil de explicar a quien revisa | Medio; añade un proveedor |
| D. Un LLM propone el mapeo leyendo una muestra | Potente con estructuras raras | No determinista; envía valores (datos de salud) a un tercero; necesita revisión humana igualmente | Medio-alto. Encaja como **ayuda** en la fase 3, no como motor |
| E. Aplazar (script por clínica) | Nada que construir | Es justo el problema que queremos eliminar | Ninguno ahora, alto después |

## Decisión
**A**, con el mapeo explícito del perfil como válvula de escape (REQ-NOR-015). Gana porque ataca el
riesgo principal sin coste externo: cuando el reranking duda, deja el campo sin mapear y avisa en vez de
elegir (REQ-NOR-014), y el resultado se compara en los tests con un mapeo de referencia (REQ-NOR-016).
Además convierte el alta de una clínica en configuración que se acumula: cada sinónimo que se añade sirve
para las siguientes. D queda para la fase 3 como **propuesta** de perfil que aprueba una persona.

## Consecuencias
- **Positivas**: una clínica nueva entra con un perfil corto (ruta de los registros, zona horaria, formatos)
  y, solo si hace falta, mapeos explícitos; el informe explica cada decisión del mapeo.
- **Negativas / lo que aceptamos**: el diccionario es un activo que hay que versionar y revisar; los pesos
  (`peso_nombre`, `peso_contenido`, `umbral`, `margen`) son supuestos hasta medirlos con más clínicas.
- **Qué vigilamos y cuándo la revisamos**: el % de campos con `mapeo_dudoso` por clínica nueva (histórico de
  REQ-NOR-029). Si más de uno de cada cinco campos de una clínica nueva necesita mapeo explícito, revisar
  pesos o valorar C/D.

## Cómo se verifica
- `tests/unit/dominio/test_mapeo.py`: puntuaciones, umbral, margen y empates (REQ-NOR-013, REQ-NOR-014).
- `tests/integracion/test_clinicas_sin_codigo.py`: A, B y C contra su mapeo de referencia, sin cambios en
  `src/` (REQ-NOR-016, REQ-NOR-017); el alcance de T-001-5 no permite tocar `src/`.
- `make arquitectura`: el reranking vive en el dominio y no importa `yaml` ni `pydantic`.

## Diagrama
`docs/diagramas/adr-0001.html` — flujo de datos del mapeo (pendiente: `/diagrama`).
