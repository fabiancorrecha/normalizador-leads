# TASKS-NNN — Una tarea = una sesión de Claude Code = un cambio pequeño

| ID | Tarea | Requisitos | Archivos permitidos | Estado |
|----|-------|-----------|---------------------|--------|
| T-NNN-1 | [Primera porción vertical: la más pequeña que demuestra valor] | REQ-XXX-001 | `[ruta]`, `tests/[test]` | ⏳ |
| T-NNN-2 | [Caso de error / riesgo principal] | REQ-XXX-002 | `[ruta]`, `tests/[test]` | ⏳ |

IDs únicos en todo el proyecto: `T-<spec>-<n>` (p. ej. `T-002-1`, o `T-B003-1` en un bug), para que
`/implementar T-002-1` no tenga dudas sobre a qué spec pertenece.
Orden: primero lo que cubre el riesgo principal, luego el camino feliz, luego mejoras.
Cada tarea: requisitos · archivos en alcance · fuera de alcance · test primero · `make check`.
