# Diagramas con diagram-design

[diagram-design](https://github.com/cathrynlavery/diagram-design) (MIT) es un plugin de Claude Code
que genera diagramas como **un único archivo HTML + SVG** a partir de una petición en lenguaje natural.
45 tipos: recorrido de usuario, arquitectura, flujos, secuencia, estados, despliegue, Gantt…

## Instalación (una vez, dentro de Claude Code)
```text
/plugin marketplace add cathrynlavery/diagram-design
/plugin install diagram-design@diagram-design
```
La primera vez te preguntará por el estilo (colores y fuentes de tu marca, o el de por defecto).

**Revisión de seguridad hecha antes de recomendarlo** (repasa lo mismo al actualizar):
sin hooks ni servidores MCP; scripts solo locales (exportar e importar); sin telemetría.
Único acceso a red: las fuentes de Google Fonts al abrir el diagrama (Google ve la IP de quien lo
abre, no el contenido). En proyectos confidenciales, pide el diagrama con fuentes del sistema.
Instalar plugins de terceros es una decisión de confianza: revísalos siempre antes.

## Qué diagrama en cada fase
| Fase | Pregunta que responde | Tipo | Archivo |
|---|---|---|---|
| Descubrimiento | ¿Cómo lo hace hoy el usuario y dónde duele? | User journey | `recorrido-actual.html` |
| Descubrimiento | ¿Cómo funcionará la idea, de punta a punta? | Service blueprint / process / high-level | `como-funcionara.html` |
| Spec | ¿Qué pasa en cada caso, incluidos los errores? | Flowchart / sequence / state machine | `spec-NNN-*.html` |
| Arquitectura (ADR) | ¿Qué piezas hay y dónde está cada límite? | Architecture / architecture delta / data flow | `adr-NNNN.html` |
| Datos | ¿Qué entidades hay y cómo se relacionan? | ER / database schema | `datos.html` |
| Riesgos | ¿Dónde se aplica cada control? | Layer stack (controles) / architecture (*secure paved road*) | `controles.html` |
| Plan | ¿En qué orden y con qué hitos? | Gantt / timeline / lifecycle | `fases.html` |
| Despliegue | ¿Dónde corre cada cosa y cómo llega a producción? | Deployment | `despliegue.html` |

## Reglas
- Un diagrama por pregunta. Si tiene más de 9 nodos, probablemente son dos diagramas.
- Los diagramas son código: viven en `docs/diagramas/`, se versionan y se revisan en el PR.
- Si un cambio altera la arquitectura o un flujo, **su diagrama se actualiza en el mismo cambio**.
- Nunca datos reales de clientes ni de personas en un diagrama: solo ejemplos sintéticos.
- El diagrama explica; la spec y los tests mandan. Si se contradicen, gana el test.
