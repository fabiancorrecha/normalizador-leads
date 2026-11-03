# Prueba técnica - AI Product Engineer

**Tiempo: 35 minutos de trabajo.** Compartiendo pantalla, con tus herramientas habituales.

---

## El contexto

En VidasPrime captamos pacientes internacionales para clínicas y hospitales. Cada centro nos manda sus consultas entrantes (leads) exportadas desde su propio sistema, y cada uno lo hace a su manera: distintos nombres de campo, distinta estructura, distintos formatos de fecha, y el mensaje del paciente en texto libre y en cualquier idioma.

Hoy, cada vez que entra una clínica nueva, alguien escribe un script a medida para ese centro. Queremos dejar de hacer eso.

## El encargo

Tienes dos ficheros:

- `clinica_a_leads.json` - export del CRM de un centro
- `clinica_b_leads.json` - export de un centro distinto

Construye un pequeño módulo en Python que los normalice a un **esquema común** y que pueda absorber un tercer centro **sin tocar el código**.

### Esquema de salida objetivo

| Campo | Notas |
|---|---|
| `lead_id` | Identificador único |
| `source` | Centro de origen |
| `full_name` | Nombre completo, limpio |
| `email` | Normalizado, o `null` |
| `phone` | Formato internacional |
| `country` | Criterio tuyo, pero consistente entre centros |
| `created_at` | ISO 8601 en UTC |
| `enquiry_text` | Texto original del paciente |
| `specialty` | Extraído del texto libre |
| `urgency` | `alta` / `media` / `baja`, extraído del texto |
| `has_reports` | `true` / `false` / `null`, extraído del texto |
| `language` | Idioma del paciente |

---

## Tareas, por orden de prioridad

**1. Normalización (núcleo).**
Lleva la clínica A al esquema común. Los datos vienen como vienen de un sistema real: espera inconsistencias.

**2. Extracción del texto libre.**
Los campos `specialty`, `urgency`, `has_reports` y `language` están dentro del mensaje del paciente, en prosa y en varios idiomas. Resuélvelo como te parezca mejor.

**3. Configurabilidad (lo que más nos interesa).**
Haz que la clínica B funcione **sin modificar el código**: solo configuración. Si lo consigues, demuéstralo ejecutándolo.

**4. Productivización (solo contarlo, no hace falta implementarlo).**
En los últimos minutos, cuéntanos cómo llevarías esto a producción como módulo de un producto: qué falta, dónde se rompe, qué harías distinto si lo fuesen a usar quince clínicas.

---

## Cómo queremos que trabajes

- **Usa todo lo que usas normalmente.** Claude Code, tu editor, tus plantillas, lo que sea. Es exactamente lo que queremos ver.
- **Piensa en voz alta.** Nos interesa más tu razonamiento que el resultado.
- **Pregunta lo que necesites.** Hay cosas en el enunciado y en los datos que están sin decidir a propósito.

## Qué NO estamos evaluando

- Que termines las cuatro tareas. **No da tiempo, y lo sabemos.** Preferimos dos cosas bien pensadas que cuatro a medias.
- Que el código esté pulido, tenga tests completos o la cobertura sea perfecta.
- Que aciertes a la primera.
