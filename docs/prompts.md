# Prompts listos para la prueba

## Fórmula para cualquier instrucción
**Contexto · Objetivo · Restricciones · Fuera de alcance · Cómo se verifica**

```
Contexto: [qué es el proyecto]. Lee CLAUDE.md y specs/NNN/spec.md.
Objetivo: implementa REQ-XXX-001 ([en palabras]).
Restricciones: toca solo [rutas]; datos sintéticos; [regla del riesgo principal].
Fuera de alcance: [lo que no quieres que toque].
Verificación: primero escribe el test que lo demuestre, ejecútalo y enséñame que falla;
luego implementa y enséñame la salida completa de `make check` en verde.
```

## 0. Descubrimiento (solo si partes de una idea, antes de la spec)
```
Tengo esta idea: [idea en 2-3 frases]. Antes de construir nada, ayúdame a rellenar
docs/descubrimiento.md: problema, hipótesis medible, los 4 riesgos (valor, usabilidad,
viabilidad, negocio) y el experimento más barato para el riesgo más alto.
Cuestiona la idea: dime qué tendría que ser verdad para que funcione y qué la mataría.
Después, con diagram-design, dibuja el recorrido actual del usuario y cómo funcionaría
con la solución (docs/diagramas/). No escribas código.
```

## 1. Arranque (en modo Plan: Shift+Tab hasta "plan mode")
```
Vamos a construir [producto] para [usuario], que resuelve [problema].
Éxito = [métrica]. Riesgo principal = [lo peor que puede pasar].
Antes de escribir código: hazme las preguntas que necesites, lista tus supuestos
y propón un plan de máximo 6 pasos con el riesgo de cada uno y cómo lo verificarás.
No toques archivos hasta que lo apruebe.
```

## 2. Rellenar el kit
```
Con lo que hemos acordado, rellena CLAUDE.md (sección Producto, reglas 1 y mapa del código),
docs/riesgos.md (máx. 3 riesgos) y crea specs/001-[nombre]/spec.md y tasks.md
a partir de specs/_plantilla. Requisitos en formato EARS, testeables, con ID.
Incluye un apartado "Fuera de alcance". Enséñamelos antes de seguir.
```

## 3. Implementar una tarea
```
/implementar T-001
```

## 4. Exigir evidencia
```
Ejecuta `make check` y pega la salida completa. No la resumas ni digas que funciona sin ella.
```

## 5. Autocrítica
```
¿Qué podría fallar en producción con [10x usuarios / datos reales / un usuario malicioso]?
Dame los 3 riesgos principales, cuál cubre ya un test y cuál no.
```

## 6. Revisión independiente
```
Usa el subagente revisor sobre el diff actual. Solo hallazgos con escenario concreto.
```

## 7. Reconducir (cuando se desvía)
```
Para. Te estás saliendo del alcance de T-001. Deshaz [X] y vuelve solo a REQ-XXX-001.
```
Atajos: **Esc** para · **Esc Esc** vuelve a un punto anterior · `/clear` entre tareas.

## 8. Convertir un error en sistema
```
Has cometido [error]. Propón la regla mínima para CLAUDE.md, o un caso de test, o una regla
de guardrail para .claude/hooks/reglas_proyecto.py con su caso en tests/test_reglas_proyecto.py
(uno que bloquee y uno legítimo que no), que evite que vuelva a pasar. No la apliques: enséñamela.
```

## 9. Cierre
```
/cierre
```

## 10. Decisión de arquitectura (ADR)
```
Necesito decidir [decisión difícil de revertir]. Propón un ADR en docs/adr/ con la plantilla
0000-plantilla.md: al menos 2 alternativas reales más "aplazar", ligadas a los riesgos de
docs/riesgos.md, y cómo verificaríamos la decisión en el código. Dibuja con diagram-design
la arquitectura resultante (o el antes/después) en docs/diagramas/adr-NNNN.html.
No elijas tú: recomiéndame una y espera.
```

## 11. Diagrama para explicar
```
Con diagram-design, dibuja [qué] para que [quién] entienda [qué pregunta] en 30 segundos.
Máximo 9 nodos; resalta solo lo que importa ([riesgo / cambio / cuello de botella]).
Guárdalo en docs/diagramas/[nombre].html. Solo datos de ejemplo, nada real.
```

## 12. Preparar un lanzamiento
```
Prepara el lanzamiento de [spec/feature] siguiendo docs/checklists/lanzamiento.md,
seguridad.md y observabilidad.md. Para cada punto dime: hecho (con evidencia), pendiente,
o no aplica (y por qué). No despliegues nada: el despliegue lo hace el pipeline.
```
