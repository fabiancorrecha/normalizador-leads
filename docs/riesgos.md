# Matriz riesgo → control

Para cada riesgo principal (1 a 3, no más) define las tres columnas. Así la calidad se diseña
según lo que puede salir mal en ESTE proyecto, no de forma genérica.

| Riesgo (lo peor que puede pasar) | Requisito en la spec | Guardrail que lo protege | Test / eval que lo mide |
|---|---|---|---|
| [RELLENAR] | REQ-XXX-NNN | [hook, permiso, revisión obligatoria…] | [nombre del test o eval] |

Cuando definas el guardrail, añade su regla en `.claude/hooks/reglas_proyecto.py` (lista `BASH` para
comandos, `ARCHIVOS` para contenido) y, en `tests/test_reglas_proyecto.py`, un caso que debe bloquearse
y uno legítimo parecido que debe pasar. Ese archivo lo editas tú: Claude no puede tocar sus guardrails.

## Ejemplos para adaptar
| Tipo de proyecto | Riesgo | Requisito | Guardrail | Test / eval |
|---|---|---|---|---|
| SaaS multi-cliente | Un cliente ve datos de otro | Aislamiento por cliente en la BD | Hook bloquea desactivar el aislamiento | Test cruzado cliente A vs B |
| Pagos | Cobro doble o importe erróneo | Idempotencia; importes en céntimos (enteros) | Hook bloquea `float` en módulos de dinero | Test de reintentos y redondeo |
| E-commerce | Vender sin stock | Reserva atómica de stock | Revisión humana obligatoria (CODEOWNERS) | Test de concurrencia |
| Feature con IA | Respuesta inventada o peligrosa | Solo responde con fuentes; humano en el bucle | Filtro de salida; prompt versionado | Eval con casos críticos y trampa |
| Herramienta interna | Borrado masivo de datos | Borrado lógico y reversible | Hook bloquea `DROP`/`DELETE` sin `WHERE` | Test de restauración |
| Datos personales | Fuga de datos personales | Logs solo con IDs | Hook bloquea datos personales en logs | Test que inspecciona los logs |
