# Segunda revisión de T-001-2 — hallazgos pendientes

Resultado: 0 críticos, 0 altos, 7 medios y 5 bajos. Ninguno cambia los 15 registros de ejemplo ni
bloquea A y B. Todos tocan `src/normalizador/dominio/`, que ninguna tarea posterior puede editar: para
aplicarlos hay que reactivar T-001-2 (`python3 evals/alcance.py --iniciar T-001-2`), retirar su ✅ en
`tasks.md` y volver a cerrarla con `make check` en verde.

## Medios
1. `fechas.py`, `_validar_formato`: valida cada directiva por separado, no la combinación. Una
   directiva repetida (`%d/%m/%Y %d`) lanza `re.PatternError` en la primera fecha, que no es
   `ValueError` y revienta la carga; `%I` sin `%p` lee `12:30` como las 00:30 sin aviso; `%m/%Y`
   inventa el día 1. Arreglo: contar directivas (cada una como mucho una vez; exactamente un año, un
   mes y un día; `%I` solo con `%p`), con tests REQ-NOR-018.
2. `fechas.py`, `RangoPlausible`: `dias_maximos=999_999` o una referencia centinela
   (`01/01/0001 00:00`) dan `OverflowError` en cada lead. Arreglo: en `__post_init__`, calcular los
   límites dentro de un `try` y convertir `OverflowError` en `ValueError`; precalcular el primer
   instante admitido.
3. `fechas.py`, `_lecturas_locales`: una fecha sin hora cae en la comprobación de horas repetidas o
   inexistentes cuando la zona cambia el reloj a medianoche (`America/Santiago` 06/09/2026 →
   `fecha_no_reconocida`; `America/Havana` 01/11/2026 → `fecha_ambigua`). Arreglo: si el valor no
   trae hora, usar el comienzo del día (`datetime.combine(dia, time(), tzinfo=zona)`, `fold=0`) en
   los dos caminos (strptime e ISO) y en `admite`.
4. `contacto.py`, `FORMATO_DE_EMAIL`: acepta `<juan@example.com>`, `juan@example.com;`,
   `a..b@example.com` y `juan@example.c`. Arreglo (verificado por el revisor con los 12 emails de los
   exports): `[^\s@()<>\[\]:;,\\\".]+(?:\.[^\s@()<>\[\]:;,\\\".]+)*@(?:[^\W_]+(?:-+[^\W_]+)*\.)+[^\W\d_]{2,}`.
5. `contacto.py`: el atajo `startswith("+")` decide `telefono_sin_region` antes de que phonenumbers
   mire el texto. Sin país, `(+52) 55 4412 8890` o `Tel: +52 …` dan null; y `abc` sin país da
   `telefono_sin_region` en vez de `telefono_no_valido`, lo que falsea los motivos de T-001-8 e
   impide usar `normalizar_telefono(valor, None)` como validador en T-001-3. Arreglo: llamar siempre
   a `parse`; `telefono_sin_region` solo con `INVALID_COUNTRY_CODE`, región `None` y sin `+` antes
   del primer dígito.
6. `contacto.py`: `is_possible_number` acepta números locales sin prefijo de zona (`4412 8890` + MX
   → `+5244128890` con `telefono_no_verificado`). Arreglo:
   `is_possible_number_with_reason(numero) == ValidationResult.IS_POSSIBLE`; el resto,
   `telefono_no_valido`. Los 15 registros no cambian.
7. `identidad.py`, `AliasDePaises`: «código válido» solo comprueba que sean dos letras: `UK` se
   acepta (no es ISO y los teléfonos británicos perderían la región), y un alias de dos letras que
   coincide con el código de un país ausente del diccionario se lo queda (`SA` → ZA). Arreglo: exigir
   `phonenumbers.SUPPORTED_REGIONS` y que un alias de dos letras de ese conjunto lleve a sí mismo.

## Bajos
8. `test_fechas.py`: mutantes que sobreviven: `<=` por `<` en el límite superior, y
   `referencia.astimezone(zona).date()` por `referencia.date()` (el rango de prueba está en Madrid,
   pero T-001-4 pasará la referencia en UTC). Faltan tests: `27/10/2026 08:14` sin aviso y `08:15`
   con aviso; referencia en UTC con 29/04 fuera y 30/04 dentro; `leer_fecha(campo=…)`;
   `set(REGISTROS) == set(FECHAS)` en `test_exports_de_ejemplo.py`.
9. Constructores: `LecturaDeFechas` con un generador guarda `formatos=()`; con `zona` como texto
   lanza `TypeError` en la primera fecha; `AliasDePaises({...})` directo se salta `desde`. Arreglo:
   `tuple(formatos)` antes de validar, `isinstance(zona, ZoneInfo)` y la validación de los alias en
   `__post_init__`.
10. Docstring de `leer_fecha`: con `epoch_s` declarado, cualquier entero es una fecha
    (`leer_fecha(4417)` → 1970), así que el validador del reranking debe exigir también el rango
    (REC-030).
11. `contacto.py`, `_tiene_invisibles`: solo mira Cc y Cf; pasan surrogates sueltos, caracteres de
    uso privado, U+3164 y U+2800. Arreglo: cualquier categoría `C*` más esa lista corta.
12. `identidad.py`: un nombre hecho solo de caracteres invisibles sale válido y un BOM inicial se
    conserva. Arreglo: sin ningún carácter visible → `dato_ausente`; quitar BOM y ZWSP de los extremos
    (no el ZWNJ, U+200C, que forma parte de nombres persas).

## Decisión pendiente antes de T-001-4
Perfil de A: si declara solo `dd/mm/aaaa`, el 4423 (`03/04/2026`) sale como 3 de abril con
`fecha_fuera_de_rango`; si declara también `mm/dd/aaaa`, sale null con `fecha_ambigua`, que es el
ejemplo de la spec y de `docs/riesgos.md`.
