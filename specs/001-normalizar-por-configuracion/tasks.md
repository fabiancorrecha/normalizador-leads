# TASKS-001 — Una tarea = una sesión de Claude Code = un cambio pequeño

| ID | Tarea | Capa | Requisitos | Archivos permitidos | Estado |
|----|-------|------|-----------|---------------------|--------|
| T-001-1 | Esqueleto andante: paquete con las capas, CLI que lee un export y escribe `leads.jsonl` (vacío) e `informe.json` (perfil, entrada y 0 leads; el recuento de entrada llega en T-001-4 con la ruta de registros del perfil), ruff en `LINT_CMD`, test de humo | Todas (esqueleto, sin funcionalidad) | REQ-NOR-001 | `pyproject.toml`, `requirements-dev.txt`, `README.md`, `proyecto.mk`, `.gitignore`, `src/normalizador/__init__.py`, `src/normalizador/__main__.py`, `src/normalizador/cli.py`, `src/normalizador/dominio/__init__.py`, `src/normalizador/aplicacion/__init__.py`, `src/normalizador/adaptadores/__init__.py`, `tests/unit/**`, `tests/integracion/**` | ✅ |
| T-001-2 | Normalizadores puros con avisos: fechas (formatos declarados, zona, rango), teléfono E.164, email, nombre, país ISO, `lead_id` y `enquiry_text` | dominio | REQ-NOR-004..012 | `src/normalizador/dominio/lead.py`, `src/normalizador/dominio/avisos.py`, `src/normalizador/dominio/fechas.py`, `src/normalizador/dominio/contacto.py`, `src/normalizador/dominio/identidad.py`, `tests/unit/dominio/**` | ✅ |
| T-001-3 | Diccionario semántico y reranking del mapeo (nombre + contenido, umbral y margen), mapeo explícito del perfil y validación de perfiles y diccionario | dominio → adaptadores (configuración) | REQ-NOR-013, REQ-NOR-014, REQ-NOR-015, REQ-NOR-018 | `src/normalizador/dominio/diccionario.py`, `src/normalizador/dominio/mapeo.py`, `src/normalizador/adaptadores/configuracion.py`, `config/diccionario.yaml`, `tests/unit/dominio/test_mapeo.py`, `tests/unit/adaptadores/**` | ✅ |
| T-001-4 | Pipeline ETL con cuarentena y perfil de la clínica A, de punta a punta por la CLI, con logs sin datos personales | aplicación → adaptadores → cli (de dentro afuera) | REQ-NOR-001, REQ-NOR-002, REQ-NOR-003, REQ-NOR-016, REQ-NOR-027 | `src/normalizador/aplicacion/puertos.py`, `src/normalizador/aplicacion/pipeline.py`, `src/normalizador/adaptadores/lector_json.py`, `src/normalizador/adaptadores/escritor.py`, `src/normalizador/cli.py`, `config/clinicas/clinica_a.yaml`, `tests/unit/aplicacion/**`, `tests/integracion/test_clinica_a.py`, `tests/integracion/test_sin_perdidas.py`, `tests/integracion/test_logs_sin_datos_personales.py`, `tests/integracion/conftest.py` | ✅ |
| T-001-5 | Clínica B y una tercera clínica sintética (C) solo con configuración: ningún archivo de `src/` | configuración (sin código) | REQ-NOR-016, REQ-NOR-017 | `config/clinicas/clinica_b.yaml`, `config/clinicas/clinica_c.yaml`, `config/diccionario.yaml`, `tests/datos/clinica_c_leads.json`, `tests/integracion/test_clinicas_sin_codigo.py` | ✅ |
| T-001-6 | Extracción por diccionario: specialty, urgency, has_reports y language, con el puerto `Extractor` | dominio → aplicación | REQ-NOR-019..023 | `src/normalizador/dominio/extraccion.py`, `src/normalizador/aplicacion/puertos.py`, `src/normalizador/aplicacion/pipeline.py`, `src/normalizador/cli.py`, `config/diccionario.yaml`, `tests/unit/dominio/test_extraccion.py`, `tests/integracion/test_extraccion_clinicas.py`, `tests/integracion/test_clinica_a.py`, `tests/integracion/test_clinicas_sin_codigo.py` | ✅ |
| T-001-7 | Extractor con LLM tras el puerto: salida estructurada validada, timeout, respaldo por diccionario, enmascarado del documento de identidad y prompt versionado con casos (necesita ADR-0002 Aceptado) | adaptadores + prompts | REQ-NOR-024, REQ-NOR-025, REQ-NOR-026 | `src/normalizador/dominio/enmascarado.py`, `src/normalizador/adaptadores/extractor_llm.py`, `src/normalizador/cli.py`, `pyproject.toml`, `requirements-dev.txt`, `proyecto.mk`, `.env.example`, `config/diccionario.yaml`, `prompts/extraccion-lead/v1.md`, `prompts/extraccion-lead/casos.jsonl`, `prompts/extraccion-lead/resultados/**`, `tests/unit/dominio/test_enmascarado.py`, `tests/unit/adaptadores/test_extractor_llm.py` | ✅ |
| T-001-8 | Flag de calidad: informe por campo, campos no mapeados, posibles duplicados e histórico acumulado e idempotente, solo con agregados | dominio → aplicación → adaptadores | REQ-NOR-028, REQ-NOR-029, REQ-NOR-030 | `src/normalizador/dominio/calidad.py`, `src/normalizador/aplicacion/informe.py`, `src/normalizador/aplicacion/puertos.py`, `src/normalizador/aplicacion/pipeline.py`, `src/normalizador/adaptadores/historico_jsonl.py`, `src/normalizador/cli.py`, `tests/unit/dominio/test_calidad.py`, `tests/integracion/test_historico.py` | ⏳ |

IDs únicos en todo el proyecto: `T-<spec>-<n>` (p. ej. `T-002-1`, o `T-B003-1` en un bug), para que
`/implementar T-002-1` no tenga dudas sobre a qué spec pertenece.
Orden: el esqueleto; después el riesgo principal (T-001-2 no adivina datos, T-001-4 no pierde registros);
después la métrica (T-001-3 y T-001-5) y al final la extracción y el flag. Dependencias lógicas, que
`alcance.py --solapes` no ve porque solo mira archivos: T-001-4 usa el dominio de T-001-2 y el mapeo de
T-001-3; T-001-5 necesita el pipeline de T-001-4; T-001-7 necesita el puerto de T-001-6 y el ADR-0002
aceptado; T-001-8 necesita el pipeline. La fase va en serie, en el orden de la tabla.
Cada tarea: requisitos · archivos en alcance · fuera de alcance · test primero · `make check`.
Convención de los tests: el ID del requisito va en el nombre, en mayúsculas
(`test_REQ_NOR_004_fecha_ambigua_queda_null_con_aviso`); así lo lee `make coverage` en el informe JUnit.

## Detalle por tarea

### T-001-1 — Esqueleto andante
- `pyproject.toml`: paquete `normalizador` en `src/`, Python 3.13, dependencias fijadas (pydantic v2, PyYAML,
  phonenumbers). Configuración de pytest (`pythonpath = ["src"]`) y de ruff, que excluye las piezas del kit
  (`evals/`, `.claude/`, `prompts/`, `tests/carga/`, `tests/e2e/`, `tests/test_{guardrails,reglas_proyecto,kit}.py`).
- `requirements-dev.txt`: pytest, ruff y el propio proyecto (`-e .`); la CI lo instala.
- `proyecto.mk`: activa `LINT_CMD = $(PY) -m ruff check . && $(PY) -m ruff format --check .`: todo el
  código propio, con las piezas del kit y los `*.md` fuera por `extend-exclude`.
- `cli.py` es la raíz de composición: lee los argumentos, carga la configuración y conecta el pipeline con
  sus adaptadores. En esta tarea solo lee el export y escribe los dos archivos.
- `.gitignore`: añade `salida/` y `datos/` (leads normalizados e histórico: datos de salud, fuera de git).
- Sin despliegue: es una CLI local (el «entorno de pruebas» del esqueleto es `make check`).
- Fuera de alcance: cualquier normalización real.

### T-001-2 — Normalizadores puros
- Funciones puras que devuelven `(valor | None, avisos)`; nunca lanzan por un dato malo del paciente: un dato
  malo es un aviso, no una excepción.
- Fechas: lista ordenada de formatos del perfil (`%d/%m/%Y`, `%Y-%m-%d`, `%d-%b-%Y` con meses en español,
  `epoch_s`, ISO 8601 con desfase); un valor que encaja en dos formatos con resultados distintos es
  `fecha_ambigua`. El reloj y la fecha del export se inyectan: nada de `datetime.now()` en el dominio.
- Teléfono con `phonenumbers`, región = país del propio lead; país con los alias del diccionario.
- Casos mínimos: los 10 registros de A y los 5 de B (`docs/`), incluido `03/04/2026`, el epoch del 4421,
  `07700 900182` y `"  Mariam  Khoury "`.
- Fuera de alcance: leer archivos o configuración (eso es de los adaptadores).

### T-001-3 — Diccionario semántico y reranking
- `config/diccionario.yaml`: por campo del esquema, sinónimos en varios idiomas (`email`: mail, correo,
  e-mail…), composiciones (`full_name` ← `first_name` + `last_name`), validador del contenido, pesos
  (`peso_nombre`, `peso_contenido`), `umbral` y `margen`; alias de países y catálogo de especialidades (este
  último lo usa T-001-6).
- Reranking: los candidatos salen de recorrer el registro (también objetos anidados, `contacto.email`) y se
  puntúan por nombre (sinónimo exacto, normalizado) y por el % de valores de la columna que pasan el
  validador. Un mismo campo de origen con valores de dos tipos (`contacto` como objeto o como texto en el
  4421) se resuelve por contenido.
- Validación con pydantic en `adaptadores/configuracion.py` (REQ-NOR-018); el dominio recibe dataclasses.
- Fuera de alcance: embeddings o LLM para el mapeo (ADR-0001).

### T-001-4 — Pipeline ETL y clínica A
- `pipeline.py`: extraer registros (ruta a la lista en el perfil: `registros` en A, raíz en B) → mapear →
  normalizar → extraer del texto (puerto; en esta tarea, un extractor nulo) → validar → cargar.
- Cuarentena en `<salida>/cuarentena.jsonl` con `lead_id` (si existe), índice del registro y motivo.
- `config/clinicas/clinica_a.yaml`: `source`, ruta a los registros, zona horaria, formatos de fecha, fecha
  del export (`exportado`), antigüedad máxima.
- Logs con `logging` y campos fijos (`lead_id`, `perfil`, `motivo`); el test captura los logs y comprueba que
  no aparece ningún nombre, email, teléfono ni texto de los exports.
- Fuera de alcance: B y C, la extracción real, el histórico.

### T-001-5 — B y C solo con configuración
- Solo archivos de `config/` y de `tests/`: si hace falta tocar `src/`, la tarea se detiene y se propone un
  cambio a la spec (es justo lo que la métrica prohíbe).
- `tests/datos/clinica_c_leads.json`: 5-8 registros sintéticos con otra estructura (p. ej. CSV convertido a
  JSON con `correo_electronico`, `telefono_movil`, `fecha_registro` en `mm/dd/aaaa` y `nacionalidad`).
- El test compara el mapeo propuesto con el mapeo de referencia de A, B y C, campo a campo.

### T-001-6 — Extracción por diccionario
- Catálogo de especialidades, señales de urgencia y de informes en varios idiomas (es, en, ru, pl, it, fr,
  de, pt) en `config/diccionario.yaml`; idioma por alfabeto y palabras frecuentes.
- El puerto `Extractor` (`Protocol`) en `aplicacion/puertos.py`; el pipeline lo recibe por parámetro.
- Casos: 4417 traumatología/alta/true/es, 4419 reproducción asistida/baja/false/en, 4421 oncología/alta (la
  gravedad manda sobre el plazo de diciembre)/true/fr, 4422 oftalmología/baja/null/de, 4423 vacío → nulos y
  media, 0883 oncología/alta/true/en.

### T-001-7 — Extractor con LLM
- Requiere ADR-0002 en estado Aceptada; si no lo está, la tarea no empieza.
- `anthropic` con `client.messages.parse(...)` y un modelo pydantic con enums; timeout y `max_retries`
  explícitos; si `stop_reason` es `refusal`, la salida no es válida o hay error, respaldo por diccionario.
- El texto del paciente va delimitado como dato; los documentos de identidad se enmascaran antes de enviarlo.
- `prompts/extraccion-lead/v1.md` (`estado: borrador`) y `casos.jsonl` con `"requisitos"`; casos `critico`:
  el 4424 nunca `alta`, oncología avanzada (0883) siempre `alta`, el 4422 sin su documento en el texto enviado.
- Los tests usan un cliente falso; `make eval-ia` solo con permiso (cuesta dinero).

### T-001-8 — Flag de calidad e histórico
- Informe por clínica y campo: % de valores con aviso y sus motivos, campos no mapeados, posibles duplicados.
- Histórico en `datos/historico_calidad.jsonl` (ruta configurable, fuera de git), detrás del puerto
  `Historico`: una línea por carga con la huella del export y del perfil, y solo agregados.
- El informe compara la clínica con el acumulado anterior (p. ej. «`created_at`: 30 % con aviso en
  clinica_a frente al 0 % acumulado»).
