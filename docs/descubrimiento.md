# Descubrimiento — Normalizador de leads por configuración

Objetivo: decidir **con evidencia** si merece la pena construirlo, ANTES de escribir la spec.
Tiempo: horas, no semanas. Rellénalo con Claude en modo Plan (`docs/prompts.md` §0).

## 1. Problema
- **Quién lo sufre**: el equipo de VidasPrime que integra clínicas y hospitales y contacta a los pacientes
  internacionales que llegan por ellos.
- **Qué hace hoy** (alternativa actual): un script a medida por cada clínica nueva, que lee su export
  (estructura, nombres de campo y formatos propios) y lo convierte a mano.
- **Por qué duele**: cada clínica nueva es trabajo de desarrollo y mantenimiento propio; los errores de un
  script (fechas al revés, teléfonos sin prefijo) llegan en silencio al equipo comercial. · **Evidencia**:
  lo declara negocio en el brief (`docs/BRIEF_candidato.md`) y lo muestran los dos exports de ejemplo, que
  no comparten ni un solo nombre de campo ni la estructura. Supuesto: no hay cifras de horas por clínica.

## 2. Hipótesis
> Creemos que **un normalizador con diccionario semántico, reranking y perfiles de clínica** para **el equipo
> que integra clínicas** conseguirá **que una clínica nueva entre solo con configuración**.
> Lo sabremos cuando **los cambios de código por clínica nueva** pasen de **un script por clínica** a **cero**
> en **la fase 1** (A, B y una tercera sintética), sin perder ningún registro.

## 3. Los cuatro riesgos del producto
| Riesgo | Pregunta | Nivel | Cómo lo reducimos antes de construir |
|---|---|---|---|
| Valor | ¿Lo quieren? ¿Lo pagarían? | bajo | Lo pide negocio en el brief: el coste del script por clínica ya se paga hoy |
| Usabilidad | ¿Sabrán usarlo sin ayuda? | medio | Fase 1 es una CLI para el equipo técnico; el alta en autoservicio (fase 3) necesitará probarse con quien da de alta clínicas |
| Viabilidad técnica | ¿Podemos construirlo? Si usa IA: ¿es suficientemente fiable? | medio | Los tests de la métrica (A, B y C sin código) y el eval de la extracción con casos críticos (`make eval-ia`, con permiso) |
| Negocio | ¿Encaja en lo legal, comercial y de costes? | alto | Datos de salud (RGPD, art. 9): DPA con el proveedor de IA y visto bueno del DPO antes de datos reales (REC-001); coste por lead medido en el eval |

## 4. Cómo funcionará (diagramas)
- **Hoy**: recorrido actual del usuario → `docs/diagramas/recorrido-actual.html` (pendiente: `/diagrama`)
- **Con la solución**: cómo funcionará → `docs/diagramas/como-funcionara.html` (pendiente: `/diagrama`)
Generados con diagram-design (`docs/diagramas/README.md`). Un diagrama que no se entiende en
30 segundos es una idea que aún no está clara.

## 5. Experimento más barato
| Experimento | Riesgo que reduce | Coste | Criterio de éxito (definido ANTES) |
|---|---|---|---|
| Normalizar B y una tercera clínica sintética sin tocar `src/` (T-001-5) | Viabilidad técnica | 1 tarea | Mapeo idéntico al de referencia en todos los campos del export y 0 registros perdidos |
| Eval de la extracción con los 15 leads de ejemplo y casos críticos | Viabilidad técnica (IA) | Pocos euros, con permiso | 100 % en los casos `critico` y el respaldo por diccionario en menos del 5 % de los leads |

**Si la idea usa IA**: antes de construir producto, junta 20-50 casos reales (anonimizados), escribe
los checks en `prompts/<funcionalidad>/casos.jsonl` y mide con `make eval-ia` (`prompts/README.md`). Si la tasa de acierto no alcanza lo que el valor exige,
la idea cambia (más humano en el bucle, alcance menor) o se para.

## 6. Alcance mínimo (MVP)
- **Dentro**: la spec 001: normalizar A, B y C por configuración, con cuarentena, extracción del texto
  (diccionario y LLM con respaldo) y flag de calidad acumulado.
- **Fuera**: entrada continua, cuarentena con interfaz, fusión de duplicados, autoservicio, multi-cliente y
  despliegue (fases 2 y 3).

## 7. Decisión
- [x] **Seguir** → `specs/001-normalizar-por-configuracion/spec.md` · [ ] **Pivotar** → [qué cambia] · [ ] **Parar**
- Motivo: el problema lo declara negocio y el experimento más barato es la propia fase 1 · Decide: Producto
  (pendiente de confirmar) · Fecha: 2026-11-03
