# Normalizador de leads

Módulo del SaaS de VidasPrime que lleva los leads de cualquier clínica a un **esquema común** solo con
configuración: una clínica nueva entra con su perfil en `config/clinicas/`, sin tocar el código. Un
**diccionario semántico** (`config/diccionario.yaml`) propone qué campo del export es cada campo del
esquema y un **reranking** por nombre y contenido decide, sin adivinar: lo que no está claro queda en
`null` con un aviso, y ningún registro se pierde (normalizado o en cuarentena con motivo).

Nace de la prueba técnica de [`docs/BRIEF_candidato.md`](docs/BRIEF_candidato.md) (normalizar la clínica A,
extraer del texto libre, que la clínica B entre sin tocar código y contar cómo se productiviza), hecha con
calidad de producción y **solo con datos sintéticos**, que se tratan como datos de salud.

- [Qué hace](#qué-hace)
- [Puesta en marcha](#puesta-en-marcha)
- [Cómo funciona](#cómo-funciona)
- [Uso de la CLI](#uso-de-la-cli)
- [Añadir una clínica](#añadir-una-clínica)
- [Calidad](#calidad)
- [Documentos](#documentos)
- [Estado](#estado)

## Qué hace

- **Mapea los campos del export solo**: el diccionario de sinónimos (en español, inglés, francés, italiano,
  alemán, polaco, ruso y portugués) y un reranking por nombre y por contenido (pesos 0,5 y 0,5, umbral 0,6,
  margen 0,15 entre los dos mejores) eligen qué campo del export es cada campo del esquema. Entiende rutas
  anidadas (`contacto.email`, `datos.leads`) y nombres en dos campos (`first_name` + `last_name`). Un
  mapeo dudoso no se usa: queda avisado y el perfil de la clínica lo fija con `mapeo:`.
- **Normaliza al esquema común de 12 campos** (`lead_id`, `source`, `full_name`, `email`, `phone`,
  `country`, `created_at`, `enquiry_text`, `specialty`, `urgency`, `has_reports`, `language`): identificador
  `clinica:id`, nombre limpio, email en minúsculas y validado, teléfono en E.164 (`phonenumbers`) con la
  región del país del lead, país en ISO 3166-1 alfa-2 por una tabla de alias en varios idiomas, fecha en
  UTC desde la zona horaria de la clínica y con los formatos que declara su perfil (`dd/mm`, `mm/dd`,
  ISO 8601, epoch, mes en texto), y el texto del paciente intacto.
- **No adivina nunca**: una fecha con dos lecturas, una fecha fuera del rango plausible, un teléfono que no
  se puede verificar, un país desconocido o un dato ausente salen como `null` con un aviso de código
  estable (`fecha_ambigua`, `fecha_fuera_de_rango`, `telefono_no_verificado`, `pais_desconocido`,
  `dato_ausente`…) en el informe, nunca como un valor inventado.
- **Extrae del texto libre** `specialty`, `urgency`, `has_reports` y `language`, en el idioma en que escriba
  el paciente, por dos vías: un extractor por **diccionario** (reglas, sin red ni coste) y un extractor con
  **Claude** (salida estructurada validada contra un catálogo cerrado, texto enmascarado y tratado como
  dato, y el diccionario de respaldo si el modelo falla).
- **Cuarentena con motivo** para lo que no se puede normalizar (`registro_no_valido`, `sin_identificador`,
  `identificador_repetido`): registros de entrada = leads + cuarentena, siempre.
- **Informe de calidad por carga**: el mapeo elegido con todos sus candidatos y puntuaciones, los avisos por
  lead y campo (nunca valores), el porcentaje de leads con aviso por campo, los campos del export que no se
  han usado y los posibles duplicados por email o teléfono.
- **Histórico acumulado**: cada carga se compara con las anteriores de la clínica y de todas; una misma carga
  (mismo export, perfil, diccionario y extractor) no se cuenta dos veces. Solo agregados.
- **Privacidad por diseño**: logs e histórico sin nombre, email, teléfono ni texto; documentos de identidad
  enmascarados antes de llegar al modelo; las salidas y el histórico quedan fuera de git.
- **Configuración validada antes de empezar**: un diccionario, perfil o prompt inválidos paran la carga con
  el archivo y el campo que fallan, y no se escribe nada.

## Puesta en marcha

Necesita Python 3.13 o superior (probado en macOS; en Linux es igual). Un solo comando prepara el entorno
y normaliza los tres exports de ejemplo:

```bash
git clone https://github.com/fabiancorrecha/normalizador-leads.git
cd normalizador-leads
python3 lanzar.py
```

[`lanzar.py`](lanzar.py) crea `.venv/` si no existe, instala `requirements-dev.txt` y lanza la CLI sobre la
clínica A, la B y la C sintética, escribiendo en `salida/<clinica>/`. Opciones:

```bash
python3 lanzar.py --extractor claude   # extrae con Claude: necesita la clave de la API y cuesta dinero
python3 lanzar.py --salida otra/carpeta
```

A mano, sin el script:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m normalizador --clinica clinica_a --entrada docs/clinica_a_leads.json --salida salida/clinica_a
```

**Clave de la API** (solo para `--extractor claude`): copia `.env.example` a `.env.dev` y pon ahí
`ANTHROPIC_API_KEY`; `.env` y `.env.dev` están en `.gitignore`. También vale la variable de entorno o el
perfil de `ant auth login`. Sin clave, el extractor por diccionario funciona igual y nada llama a la red.

**Como módulo del producto**: es un paquete Python normal (`pip install .`) que se puede ejecutar como CLI
en un trabajo programado o importar desde el SaaS (`normalizador.aplicacion.pipeline.Pipeline` con los
adaptadores de `normalizador.adaptadores`). No guarda estado entre cargas: lee un export y escribe sus
archivos; el único estado persistente es el histórico, detrás de un puerto que hoy implementa un JSONL
local. Lo que falta para producción (entrada continua, cuarentena revisable, histórico en base de datos,
evals en la CI, controles RGPD y observabilidad) y cómo se escala a quince clínicas está escrito en las
fases 2 y 3 de la [spec](specs/001-normalizar-por-configuracion/spec.md). Nada se despliega desde aquí: la
CI (`.github/workflows/`) ejecuta `make check` en cada pull request y el despliegue lo aprueba una persona.

## Cómo funciona

```
export JSON ─► 1 leer ─► 2 mapear ─► 3 normalizar ─► 4 extraer del texto ─► 5 validar ─► 6 cargar
               perfil     diccionario   por campo,      diccionario o           cuarentena    leads.jsonl
                          + reranking   en UTC          Claude + respaldo       con motivo    cuarentena.jsonl
                                                                                              informe.json
                                                                                              histórico
```

1. **Leer**. El perfil de la clínica (`config/clinicas/<clinica>.yaml`) dice dónde está la lista de registros
   (`registros: datos.leads`), su zona horaria, los formatos de fecha que usa, cuántos días de antigüedad son
   plausibles y, si el export la trae, dónde está la fecha del export. Un export o una configuración que no
   sirven paran la carga antes de escribir nada (código 1).
2. **Mapear**. Para cada campo del esquema, cada ruta del export es un candidato con una puntuación
   `0,5 × nombre + 0,5 × contenido`: el nombre se compara con los sinónimos del diccionario y el contenido
   con el validador del campo (¿parecen emails?, ¿teléfonos?, ¿fechas?). Gana el candidato que supera el
   umbral y saca margen al segundo; si no hay ninguno, el campo queda sin mapear con el aviso
   `mapeo_dudoso` o `campo_sin_mapear`. El perfil puede fijar un mapeo con `mapeo:` (sale como
   `origen: perfil`); si apunta a una ruta sin datos, la carga para.
3. **Normalizar**. Cada campo pasa por su normalizador del dominio (funciones puras, sin E/S): fechas con
   zona horaria y los formatos declarados (una fecha ambigua o inexistente por el cambio de hora queda en
   `null`), teléfonos con `phonenumbers` y la región del país del lead, países por la tabla de alias, emails
   en minúsculas. Cada problema es un aviso con código estable, no una excepción.
4. **Extraer del texto**. `specialty` sale de un catálogo cerrado (gana la especialidad con más señales);
   `urgency` sigue el orden gravedad → baja → alta → media (una oncología avanzada nunca sale `baja` por
   decir «no tengo prisa»); `has_reports` mira primero las negaciones; `language` lo decide el alfabeto o
   las palabras frecuentes de cada idioma (ISO 639-1). Con `--extractor claude`, el modelo recibe el texto
   enmascarado y delimitado como dato y devuelve una salida estructurada que se valida contra el mismo
   catálogo; si falla, se niega o no vale, el lead se extrae con el diccionario y lleva el aviso
   `extraccion_respaldo`.
5. **Validar**. Un registro que no es un objeto, sin identificador o con un identificador repetido va a
   `cuarentena.jsonl` con su índice y su motivo. Nada se descarta en silencio.
6. **Cargar**. `leads.jsonl`, `cuarentena.jsonl` e `informe.json` se escriben de forma atómica (el informe
   el último) y la carga se anota en el histórico con su huella (SHA-256 del export, del perfil, del
   diccionario y del extractor): repetir una carga no la cuenta dos veces.

La arquitectura es un ETL hexagonal (`dominio` ← `aplicacion` ← `adaptadores` ← `cli`): las reglas viven en
el dominio y se prueban sin red, sin archivos y sin modelo; la E/S y la IA están detrás de puertos. Las
reglas de dependencia las comprueba `make arquitectura` y están en [`docs/arquitectura.md`](docs/arquitectura.md).

## Uso de la CLI

Desde la raíz del repositorio (las rutas por defecto, `config/`, `prompts/` y `datos/`, son relativas):

```bash
.venv/bin/python -m normalizador --clinica clinica_a --entrada docs/clinica_a_leads.json --salida salida/clinica_a
.venv/bin/python -m normalizador --clinica clinica_b --entrada docs/clinica_b_leads.json --salida salida/clinica_b
.venv/bin/python -m normalizador --clinica clinica_c --entrada tests/datos/clinica_c_leads.json --salida salida/clinica_c
```

Cada carga escribe en la carpeta de salida (atómicamente, el informe el último):
- `leads.jsonl`: un lead por línea con los 12 campos del esquema común.
- `cuarentena.jsonl`: los registros que no se pudieron normalizar, con su índice y su motivo.
- `informe.json`: recuentos, el mapeo elegido con todos sus candidatos y puntuaciones, los avisos por lead y
  campo (nunca valores), el bloque `calidad` (% de leads con aviso por campo y sus motivos, campos del
  export sin mapear, posibles duplicados), el bloque `historico` (comparación con las cargas anteriores de
  la clínica y de todas) y el bloque `extraccion` (qué extractor, modelo y prompt se usaron).

Los logs van a la salida de error en una línea JSON por evento, solo con `lead_id`, perfil, índices y
recuentos. `salida/` y `datos/` están en `.gitignore`: lo que escriben son datos de salud.

### Opciones
| Opción | Por defecto | Qué hace |
|---|---|---|
| `--config` | `config/` | Carpeta con `diccionario.yaml` y `clinicas/<clinica>.yaml` |
| `--extractor` | `diccionario` | Cómo se extraen `specialty`, `urgency`, `has_reports` y `language` del texto: `diccionario` (reglas, sin red) o `claude` (modelo, con el diccionario de respaldo). Nunca se activa solo por tener la clave |
| `--modelo` | el del prompt | Modelo de Claude, solo con `--extractor claude` |
| `--prompt` | `prompts/extraccion-lead/v1.md` | Versión del prompt de extracción, la misma que evalúa `make eval-ia` |
| `--historico` | `datos/historico_calidad.jsonl` | Histórico acumulado de calidad, solo con agregados; una misma carga no se anota dos veces |

### Códigos de salida
| Código | Cuándo | Qué queda escrito |
|---|---|---|
| 0 | Carga completa | Los tres archivos de salida y la entrada del histórico |
| 1 | Configuración, prompt, histórico o export que no sirven (con el archivo y el campo), o la API de Claude mal configurada | Nada |
| 2 | Argumentos incorrectos | Nada |

### Extracción con Claude
`--extractor claude` lee la clave de la API de la variable `ANTHROPIC_API_KEY`, del archivo `.env` o
`.env.dev` o del perfil de `ant auth login`. El texto del paciente viaja enmascarado (documentos de
identidad) y delimitado como dato; si el modelo falla, se niega o su salida no vale, el lead se extrae con el
diccionario y lleva el aviso `extraccion_respaldo`. Una clave o un modelo mal configurados paran la carga.
Cuesta dinero: unos 0,004 $ por lead con `claude-opus-5-5`. El prompt está versionado en
[`prompts/extraccion-lead/v1.md`](prompts/extraccion-lead/v1.md) con sus casos de eval, entre ellos los
críticos (la inyección de instrucciones del lead 4424 nunca sube la urgencia).

## Añadir una clínica
Un archivo `config/clinicas/<clinica>.yaml` con `source`, la ruta a la lista de registros, la zona horaria,
los formatos de fecha y, si el export la trae, dónde está la fecha del export
([`config/clinicas/clinica_c.yaml`](config/clinicas/clinica_c.yaml) es el ejemplo completo). El diccionario
resuelve el mapeo; si un campo queda dudoso, el perfil lo fija con `mapeo:`. Si hace falta un sinónimo, un
alias de país o una señal de extracción nuevos, se añaden a `config/diccionario.yaml` y sirven para todas.
El código no cambia: lo comprueba `tests/integracion/test_clinicas_sin_codigo.py`.

## Calidad
- `make check`: tests, lint (ruff), reglas de capas, cobertura de requisitos, secretos y alcance. Es la
  definición de «terminado»; la CI lo ejecuta en cada pull request.
- `make test`: solo los tests (943; nunca llaman al modelo real). Cada test lleva en el nombre el requisito
  que cubre (`test_REQ_NOR_004_…`), y `make coverage` comprueba que los 30 requisitos de la spec tienen uno.
- `make eval-ia PROMPT=prompts/extraccion-lead/v1.md`: evalúa el prompt contra sus casos (cuesta dinero).
  El último resultado real está en `prompts/extraccion-lead/resultados/`.
- Los riesgos del producto y qué requisito, guardrail y test cubre cada uno están en
  [`docs/riesgos.md`](docs/riesgos.md).

## Documentos
| Documento | Qué contiene |
|---|---|
| [`docs/BRIEF_candidato.md`](docs/BRIEF_candidato.md) | El encargo: esquema de salida y las cuatro tareas |
| [`docs/clinica_a_leads.json`](docs/clinica_a_leads.json), [`docs/clinica_b_leads.json`](docs/clinica_b_leads.json) | Los exports de ejemplo del encargo (sintéticos) |
| [`tests/datos/clinica_c_leads.json`](tests/datos/clinica_c_leads.json), [`config/clinicas/clinica_c.yaml`](config/clinicas/clinica_c.yaml) | La tercera clínica, sintética, que entra sin tocar código |
| [`specs/001-normalizar-por-configuracion/spec.md`](specs/001-normalizar-por-configuracion/spec.md) | Requisitos REQ-NOR-001 a 030, riesgos, fuera de alcance y las fases 2 (producción) y 3 (quince clínicas) |
| [`specs/001-normalizar-por-configuracion/tasks.md`](specs/001-normalizar-por-configuracion/tasks.md), [`progreso.md`](specs/001-normalizar-por-configuracion/progreso.md) | Las ocho tareas, sus archivos permitidos y la bitácora de cada paso |
| [`docs/arquitectura.md`](docs/arquitectura.md) | Capas, responsabilidades, reglas de dependencia y convenciones |
| [`docs/adr/0001-mapeo-por-diccionario-y-reranking.md`](docs/adr/0001-mapeo-por-diccionario-y-reranking.md) | Por qué diccionario + reranking y no un LLM o reglas a medida para mapear |
| [`docs/adr/0002-extraccion-con-llm-y-diccionario.md`](docs/adr/0002-extraccion-con-llm-y-diccionario.md) | Por qué dos extractores, salida validada y respaldo por diccionario |
| [`docs/riesgos.md`](docs/riesgos.md) | Matriz riesgo → requisito → guardrail → test |
| [`docs/recomendaciones.md`](docs/recomendaciones.md) | Las mejoras propuestas (REC-001 a 049), con impacto, esfuerzo y estado |
| [`docs/descubrimiento.md`](docs/descubrimiento.md) | El problema, la hipótesis y los experimentos que la validan |
| [`config/diccionario.yaml`](config/diccionario.yaml), [`config/clinicas/`](config/clinicas/) | El diccionario semántico y un perfil por clínica |
| [`prompts/extraccion-lead/`](prompts/extraccion-lead/) | El prompt de extracción, sus casos de eval y el resultado real de la última eval |
| [`CLAUDE.md`](CLAUDE.md) | Las reglas del repositorio para trabajar con Claude Code |

## Estado
Fase 1 completa: las ocho tareas de `specs/001-normalizar-por-configuracion/tasks.md` están terminadas,
`make check` pasa (943 tests, 30 de 30 requisitos cubiertos) y el prompt de extracción tiene su eval real
(63 de 63 comprobaciones en 21 casos). Las fases 2 (producción) y 3 (quince clínicas) están descritas en la
spec; las mejoras pendientes, en `docs/recomendaciones.md`.
