# ADR-0002 — Extraemos los campos del texto libre con Claude tras un puerto y con el diccionario como respaldo

Estado: Propuesta · Fecha: 2026-11-03 · Decide: Producto, Técnico y Seguridad (DPO)
<!-- Cambia Propuesta por Aceptada tú (no el agente). Si más adelante cambia: "Reemplazada por ADR-NNNN". -->

## Contexto
`specialty`, `urgency`, `has_reports` y `language` están en el mensaje del paciente, en prosa y en muchos
idiomas (español, inglés, ruso, polaco, italiano, francés, alemán; mezclas como el 4424). Fuerzas en juego:
- **Riesgo 3** (`docs/riesgos.md`): una extracción manipulada (inyección del 4424) o errónea (oncología
  avanzada como `baja`) prioriza mal a los pacientes (REQ-NOR-024, REQ-NOR-025).
- **Riesgo 2**: el texto es un dato de salud y puede llevar un documento de identidad (4422); enviarlo a un
  proveedor lo convierte en encargado del tratamiento (RGPD, art. 28) (REQ-NOR-026).
- **Escala**: un diccionario de frases por idioma y especialidad es, en la práctica, otra forma de código a
  medida; un modelo generaliza a idiomas y redacciones nuevas.
- **Proveedor de IA**: decisión difícil de revertir según `CLAUDE.md` (regla 7).

## Opciones consideradas
| Opción | A favor | En contra | Coste y reversibilidad |
|---|---|---|---|
| A. LLM (Claude) tras el puerto `Extractor`, con salida estructurada validada contra enums, y el extractor por diccionario como respaldo | Entiende prosa en cualquier idioma; el puerto permite tests sin red y cambiar de modelo; el respaldo mantiene el servicio si el modelo falla o rechaza | Coste y latencia por lead; datos de salud a un tercero (DPA, enmascarado); necesita evals | Coste por uso (medir con `make eval-ia`). Reversible: el puerto aísla el proveedor |
| B. Solo diccionario y reglas | Determinista, gratis, sin datos fuera | Frágil con redacciones e idiomas nuevos; mantenimiento creciente | Bajo coste, alto mantenimiento |
| C. Solo LLM | Lo más rápido de montar | Sin alternativa si el modelo cae o rechaza; sin tests deterministas | Dependencia total del proveedor |
| D. Modelo propio o local (clasificador entrenado) | Datos dentro de casa | Sin datos de entrenamiento etiquetados; mucho más trabajo | Alto |

## Decisión
**A.** El diccionario de T-001-6 es a la vez el respaldo y la base de comparación del eval. Detalles para
T-001-7 (comprobados con la referencia del SDK de Python de Anthropic):
- **Modelo**: `claude-opus-5-5`, el modelo por defecto actual. Alternativa a medir: `claude-haiku-5-5`,
  más barato y rápido para una extracción corta; **la elección es tuya**: decidir con `make eval-ia` sobre
  los casos de `prompts/extraccion-lead/casos.jsonl` (cuesta dinero, con permiso).
- **Salida estructurada**: `client.messages.parse(...)` con un modelo pydantic cuyos campos son enums
  (`urgency: alta|media|baja`, catálogo de especialidades del diccionario, `has_reports: bool | None`,
  `language` ISO 639-1); lo que no valide pasa al respaldo (REQ-NOR-024).
- **Robustez**: `timeout` y `max_retries` explícitos en el cliente (el SDK reintenta 408/409/429/5xx con
  espera exponencial); comprobar `stop_reason` antes de leer el contenido. Con `claude-opus-5-5`, activar
  el respaldo de modelo en el servidor (`fallbacks: "default"`, beta `server-side-fallback-2026-07-01`); si
  aun así hay `refusal`, pasa al respaldo por diccionario.
- **Inyección**: el texto del paciente va delimitado como dato y el prompt dice que nunca contiene
  instrucciones; la salida solo puede tomar valores cerrados, así que una instrucción no puede crear un
  campo ni un valor nuevo (REQ-NOR-025).
- **Datos**: se envía solo el texto, enmascarado (REQ-NOR-026); ni nombre, ni email, ni teléfono.

## Consecuencias
- **Positivas**: extracción robusta a idiomas nuevos; el sistema sigue funcionando sin modelo.
- **Negativas / lo que aceptamos**: coste por lead; un proveedor externo con datos de salud, que exige DPA y
  revisión del DPO antes de usar datos reales (REC-001); el prompt se versiona y se evalúa como código.
- **Qué vigilamos y cuándo la revisamos**: acierto del eval por campo y casos `critico` (deben ser 100 %),
  % de leads con `extraccion_respaldo`, coste y latencia por lead. Si el respaldo supera el 5 % o un caso
  crítico falla, se para y se revisa.

## Cómo se verifica
- `tests/unit/adaptadores/test_extractor_llm.py` con un cliente falso: salida válida, inválida, timeout y
  `refusal` → respaldo y aviso (REQ-NOR-024); texto enviado sin el documento del 4422 (REQ-NOR-026).
- `prompts/extraccion-lead/casos.jsonl`: casos `critico` (4424 nunca `alta`; 0883 siempre `alta`) medidos
  con `make eval-ia` (REQ-NOR-025).
- `make arquitectura`: `anthropic` solo en la capa de adaptadores.

## Diagrama
`docs/diagramas/adr-0002.html` — flujo de la extracción con respaldo (pendiente: `/diagrama`).
