"""Reglas de guardrail propias de ESTE proyecto, derivadas de docs/riesgos.md.

Es el único archivo de hooks que personalizas: `instalar.sh --actualizar` nunca lo toca.
Cada regla es (expresión regular, motivo que leerá Claude). Por cada regla, añade en
tests/test_reglas_proyecto.py un caso que debe bloquearse y uno legítimo parecido que debe pasar.
"""

# Comandos de shell que bloquea guard_bash.py. Ejemplos:
#   (r"DISABLE\s+ROW\s+LEVEL\s+SECURITY", "Rompe el aislamiento entre clientes (CLAUDE.md regla 1)."),
#   (r"\bDELETE\s+FROM\s+[\w.]+\s*(;|[\"']|$)", "DELETE sin WHERE."),   # también psql -c "DELETE FROM t"
BASH: list[tuple[str, str]] = []

# Contenido que guard_files.py no deja escribir con Edit/Write. Un tercer elemento opcional limita la
# regla a las rutas que casen con él (relativas a la raíz del proyecto). Ejemplos:
#   (r"\bfloat\b", "Importes en céntimos (int), nunca float.", r"^src/(cobros|facturas)/"),   # pagos
#   (r"log(ger)?\.\w+\(.*\{[^}]*\b(email|nombre|dni)\b", "Datos personales en logs."),
ARCHIVOS: list[tuple[str, ...]] = []
