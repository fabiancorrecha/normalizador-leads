# Arquitectura

Estado: APROBADA · Última revisión: 2026-11-03



## Estilo y por qué

**ETL hexagonal**: extraer → transformar (funciones puras) → cargar, con la IA y la E/S detrás de puertos.

```
cli (raíz de composición)
  └─ aplicacion: pipeline ETL, informe, puertos (Extractor, Historico, LectorExport, Escritor)
       └─ dominio: esquema común, normalizadores, diccionario, reranking, extracción por diccionario, calidad
adaptadores: lector JSON, configuración YAML (validada), extractor LLM, histórico JSONL, escritor
  └─ implementan los puertos de aplicacion y usan el dominio
```

Encaja porque el valor del producto está en **reglas de transformación** (normalizar, mapear, extraer) y
el riesgo principal es corromper datos en silencio: en el dominio, esas reglas son funciones puras que se
prueban sin red, sin archivos y sin modelo. Lo que cambia de una clínica a otra vive en **configuración**
(`config/`), no en el código, y lo que puede cambiar de proveedor (el LLM, el almacén del histórico, el
formato de entrada) es un adaptador detrás de un puerto (ADR-0001, ADR-0002).

## Módulos y responsabilidades

| Módulo / carpeta | Responsabilidad | Puede depender de |
|---|---|---|
| `src/normalizador/dominio/` | Esquema común (`Lead`), avisos, normalizadores (fechas, contacto, identidad), diccionario como dataclasses, reranking del mapeo, extracción por diccionario, enmascarado y estadísticas de calidad. Sin E/S | Nada del proyecto; librerías puras (`phonenumbers`, `zoneinfo`) |
| `src/normalizador/aplicacion/` | Pipeline ETL (extraer → mapear → normalizar → extraer del texto → validar → cargar), cuarentena, informe y puertos (`Protocol`) | `dominio` |
| `src/normalizador/adaptadores/` | Leer exports JSON, cargar y validar perfiles y diccionario (YAML + pydantic), extractor con Claude, histórico JSONL, escribir `leads.jsonl` e `informe.json` | `dominio`, `aplicacion` (puertos) |
| `src/normalizador/cli.py`, `__main__.py` | Raíz de composición: argumentos, configuración y conexión de adaptadores con el pipeline | Todo |
| `config/diccionario.yaml` | Sinónimos por campo, composiciones, validadores, pesos, umbral y margen; alias de países; catálogo de especialidades y señales de urgencia, informes e idioma | — (datos) |
| `config/clinicas/*.yaml` | Un perfil por clínica: `source`, ruta a los registros, zona horaria, formatos de fecha, fecha del export, antigüedad máxima y mapeos explícitos | — (datos) |
| `prompts/extraccion-lead/` | Prompt versionado y casos de eval del extractor con LLM | — |

## Reglas de dependencia (las comprueba `make arquitectura`)

Una regla por línea: `capa <nombre>: <carpetas con comodines o paquetes externos>`, `<capa> no depende de: <capas>` y, para imports con alias en JS/TS, `alias @/ = src/`. Una línea que no se entiende es un error.

```arquitectura
capa dominio: src/normalizador/dominio/**
capa aplicacion: src/normalizador/aplicacion/**
capa adaptadores: src/normalizador/adaptadores/**, yaml, pydantic, anthropic
capa cli: src/normalizador/cli.py, src/normalizador/__main__.py
dominio no depende de: aplicacion, adaptadores, cli
aplicacion no depende de: adaptadores, cli
adaptadores no depende de: cli
```

Lo que significan:

- El dominio no importa nada del proyecto ni `yaml`, `pydantic` o `anthropic`: recibe dataclasses y devuelve
valores y avisos.
- La aplicación habla con la E/S y con el modelo solo a través de sus puertos.
- `yaml`, `pydantic` y `anthropic` solo se importan en los adaptadores.

Mientras `T-001-1` no cree las carpetas, `make arquitectura` avisa de capas sin archivos (es un aviso, no un
fallo).

## Convenciones

- **Nombres**: en español y en el idioma del dominio (`normalizar_fecha`, `aviso`, `cuarentena`, `perfil`);
los campos del esquema de salida, en inglés como los define el brief. Nada de `utils`, `helpers`, `data`.
- **Errores**: un dato malo del paciente no es una excepción, es un **aviso** con un código estable
(`fecha_ambigua`, `mapeo_dudoso`…) que va al informe. Una configuración mala sí es un error y para la
carga antes de empezar (REQ-NOR-018). Nunca se tragan excepciones.
- **Configuración y secretos**: perfiles y diccionario en `config/`, versionados; la clave de la API de IA
por entorno (`ANTHROPIC_API_KEY` o perfil de `ant auth`), nunca en el repo.
- **Logs**: `logging` estructurado con `lead_id`, `perfil`, `motivo` y tiempos; nunca nombre, email,
teléfono, texto ni valores de campos (REQ-NOR-027).
- **Tiempo**: el reloj y la fecha del export se inyectan; nada de `datetime.now()` en el dominio. Todo sale
en UTC.
- **Tests**: muchos unitarios en el dominio (con los registros de `docs/` como casos), de integración de la
CLI de punta a punta en `tests/integracion/`, y el extractor LLM con un cliente falso. El ID del requisito
va en el nombre del test, en mayúsculas.

## Escalabilidad y robustez

- Sin estado en memoria entre cargas: cada ejecución lee un export y escribe sus archivos; el único estado
persistente es el histórico, detrás del puerto `Historico` y con escrituras idempotentes (REQ-NOR-030).
- Llamadas al modelo con timeout, reintentos acotados y respaldo por diccionario (REQ-NOR-024).
- Límites conocidos y cuándo revisarlos: el export se carga entero en memoria (válido hasta decenas de miles
de registros; con exports mayores, lectura en flujo, REC-006); el histórico JSONL vale para una persona y
pocas clínicas (con varias personas o la fase 2, base de datos, REC-004).

## Decisiones

- `docs/adr/0001-mapeo-por-diccionario-y-reranking.md` (Propuesta)
- `docs/adr/0002-extraccion-con-llm-y-diccionario.md` (Propuesta)
