# Normalizador de leads

Módulo del SaaS de VidasPrime que lleva los leads de cualquier clínica a un **esquema común** solo con
configuración: una clínica nueva entra con su perfil en `config/clinicas/`, sin tocar el código. Un
**diccionario semántico** (`config/diccionario.yaml`) propone qué campo del export es cada campo del
esquema y un **reranking** por nombre y contenido decide, sin adivinar: lo que no está claro queda en
`null` con un aviso, y ningún registro se pierde (normalizado o en cuarentena con motivo).

El encargo y los exports de ejemplo están en `docs/BRIEF_candidato.md` y `docs/clinica_*_leads.json`; qué
se construye y por qué, en `specs/001-normalizar-por-configuracion/`; cómo está organizado, en
`docs/arquitectura.md`; las decisiones, en `docs/adr/`. Solo datos sintéticos: se tratan como datos de salud.

## Estado
Fase 1 completa: las ocho tareas de `specs/001-normalizar-por-configuracion/tasks.md` están terminadas,
`make check` pasa (943 tests, 30 de 30 requisitos cubiertos) y el prompt de extracción tiene su eval real
(63 de 63 casos). Las fases 2 (producción) y 3 (quince clínicas) están descritas en la spec; las mejoras
pendientes, en `docs/recomendaciones.md`.

## Instalación
Necesita Python 3.13.
```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
```

## Uso
Desde la raíz del repositorio (las rutas por defecto, `config/`, `prompts/` y `datos/`, son relativas):
```bash
.venv/bin/python -m normalizador --clinica clinica_a --entrada docs/clinica_a_leads.json --salida salida/clinica_a
.venv/bin/python -m normalizador --clinica clinica_b --entrada docs/clinica_b_leads.json --salida salida/clinica_b
.venv/bin/python -m normalizador --clinica clinica_c --entrada tests/datos/clinica_c_leads.json --salida salida/clinica_c
```
Cada carga escribe en la carpeta de salida (atómicamente, el informe el último):
- `leads.jsonl`: un lead por línea con los 12 campos del esquema común (`lead_id`, `source`, `full_name`,
  `email`, `phone`, `country`, `created_at`, `enquiry_text`, `specialty`, `urgency`, `has_reports`, `language`).
- `cuarentena.jsonl`: los registros que no se pudieron normalizar, con su índice y su motivo
  (`registro_no_valido`, `sin_identificador`, `identificador_repetido`).
- `informe.json`: recuentos, el mapeo elegido con todos sus candidatos y puntuaciones, los avisos por lead y
  campo (nunca valores), el bloque `calidad` (% de leads con aviso por campo y sus motivos, campos del
  export sin mapear, posibles duplicados) y el bloque `historico` (comparación con las cargas anteriores
  de la clínica y de todas).

`salida/` y `datos/` están en `.gitignore`: lo que escriben son datos de salud.

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
`.env.dev` (copia `.env.example`; los dos están en `.gitignore`) o del perfil de `ant auth login`. El texto
del paciente viaja enmascarado (documentos de identidad) y delimitado como dato; si el modelo falla, se
niega o su salida no vale, el lead se extrae con el diccionario y lleva el aviso `extraccion_respaldo`.
Una clave o un modelo mal configurados paran la carga. Cuesta dinero: unos 0,004 $ por lead con
`claude-opus-5-5`.

## Añadir una clínica
Un archivo `config/clinicas/<clinica>.yaml` con `source`, la ruta a la lista de registros, la zona horaria,
los formatos de fecha y, si el export la trae, dónde está la fecha del export (`config/clinicas/clinica_c.yaml`
es el ejemplo completo). El diccionario resuelve el mapeo; si un campo queda dudoso, el perfil lo fija con
`mapeo:`. Si hace falta un sinónimo nuevo, se añade a `config/diccionario.yaml` y sirve para todas.

## Calidad
- `make check`: tests, lint (ruff), reglas de capas, cobertura de requisitos, secretos y alcance.
- `make test`: solo los tests. Nunca llaman al modelo real.
- `make eval-ia PROMPT=prompts/extraccion-lead/v1.md`: evalúa el prompt contra sus casos (cuesta dinero).
