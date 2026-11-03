# Progreso de 001-normalizar-por-configuracion

Bitácora de las tareas: una línea por paso, la más reciente al final. La escribe /implementar con
`python3 evals/alcance.py --nota "…" --siguiente "…"` y la lee el hook de inicio de sesión, para que el
contexto de la tarea sobreviva a /clear, a la compactación de la conversación y a una sesión nueva.

- 2026-11-03 11:21 · T-001-1 · iniciada
- 2026-11-03 11:21 · T-001-1 · contexto: T-001-1 cubre REQ-NOR-001; archivos permitidos según tasks.md; sin ADR necesario (arquitectura aprobada); el recuento de entrada necesita la ruta de registros del perfil, que llega en T-001-4 · siguiente: proponer el plan y esperar aprobación
- 2026-11-03 11:25 · T-001-1 · plan aprobado; informe.json sin recuento en T-001-1 (perfil, entrada, leads_normalizados=0): el recuento llega en T-001-4 con la ruta de registros del perfil · siguiente: escribir tests/integracion/test_cli.py y verlo fallar
- 2026-11-03 11:26 · T-001-1 · tests primero: tests/integracion/test_cli.py (REQ-NOR-001, A y B) falla con 'No module named normalizador', la razón esperada · siguiente: pyproject, requirements-dev, paquete con capas y cli.py mínima
- 2026-11-03 11:27 · T-001-1 · implementación mínima: pyproject (deps fijadas ≥7 días), requirements-dev, capas, __main__ y cli.py; test_cli pasa (2/2); LINT_CMD con ruff sobre todo el código propio, .gitignore con salida/ y datos/, README · siguiente: make lint y make check
- 2026-11-03 11:30 · T-001-1 · make check en verde: 342 passed, lint ok, capas ok, REQ-NOR-001 test ✓ (2), alcance 15 archivos dentro; *.md fuera de ruff format y __future__ en cli.py por tests/test_kit.py · siguiente: revisión con el subagente revisor
- 2026-11-03 11:45 · T-001-1 · revisor: 0 críticos, 2 altos (CI en 3.12 frente a >=3.13: lo cambia una persona en .github/; .gitignore datos/ casaba con tests/datos/: anclado), 1 medio (test_cli solo con A) y 4 bajos corregidos (entrada en el test, README sin estado que caduca, pytest 9.1.1 por los 7 días, sin referencia a agend… · siguiente: make check, marcar ✅ y cerrar
- 2026-11-03 11:45 · T-001-1 · terminada: esqueleto andante con REQ-NOR-001 cubierto (test_cli.py con A), make check en verde y revisión aplicada; pendiente de una persona: CI de .github/ a Python 3.13 · siguiente: T-001-2 (normalizadores puros del dominio)
