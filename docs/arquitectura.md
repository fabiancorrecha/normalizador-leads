# Arquitectura

Estado: BORRADOR · Última revisión: [AAAA-MM-DD]
<!-- La rellena /kit con lo que encuentra en el código y lo que hablas con él; tú la revisas.
     Al cambiar BORRADOR por APROBADA es un contrato: el agente ya no puede editarla y sus reglas las
     comprueba `make arquitectura` en cada `make check`. Para cambiarla: un ADR y la editas tú. -->

## Estilo y por qué
[RELLENAR] [Ejemplo: monolito modular con capas (dominio → aplicación → infraestructura y API). Encaja porque hay un
solo equipo y el riesgo principal está en las reglas de negocio, que así se prueban sin base de datos.]

## Módulos y responsabilidades
| Módulo / carpeta | Responsabilidad | Puede depender de |
|---|---|---|
| [src/dominio/] | [entidades y reglas de negocio, sin E/S] | [nada del proyecto] |

## Reglas de dependencia (las comprueba `make arquitectura`)
Una regla por línea: `capa <nombre>: <carpetas con comodines o paquetes externos>`, `<capa> no depende de:
<capas>` y, para imports con alias en JS/TS, `alias @/ = src/`. Una línea que no se entiende es un error.
```arquitectura
# capa dominio: src/dominio/**
# capa aplicacion: src/aplicacion/**
# capa infraestructura: src/infraestructura/**, sqlalchemy, requests
# capa api: src/api/**, fastapi
# dominio no depende de: aplicacion, infraestructura, api
# aplicacion no depende de: infraestructura, api
```

## Convenciones
- **Nombres**: [idioma, estilo; los nombres dicen qué hacen, no cómo]
- **Errores**: [excepciones de dominio propias; nunca se tragan; se traducen a respuestas en el borde]
- **Configuración y secretos**: [por entorno, nunca en el código]
- **Logs**: [estructurados, con IDs, sin datos personales]
- **Tests**: [pirámide: muchos unitarios en dominio, de integración en infraestructura, e2e solo de los
  recorridos críticos]

## Escalabilidad y robustez
- [Sin estado en memoria entre peticiones (escala en horizontal); paginación; índices; timeouts y
  reintentos en llamadas externas; idempotencia donde se reintenta]
- Límites conocidos y cuándo revisarlos: [p. ej. "una sola BD hasta ~500 clientes: ver ADR-0002"]

## Decisiones
- [ADRs que definen esta arquitectura: `docs/adr/…`]
