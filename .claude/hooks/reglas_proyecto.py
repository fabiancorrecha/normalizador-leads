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
ARCHIVOS: list[tuple[str, ...]] = [
    # Riesgo 1: un lead mal normalizado en silencio. dateutil interpreta «a lo más probable»
    # (03/04/2026 como marzo o abril sin avisar); las fechas se leen con los formatos del perfil.
    (
        r"\b(import\s+dateutil|from\s+dateutil\b)",
        "No se adivinan fechas: usa los formatos declarados en el perfil y deja null + aviso si no encaja "
        "o es ambigua (CLAUDE.md regla 1, REQ-NOR-004).",
        r"^src/",
    ),
    # Riesgo 1: un error tragado es un registro perdido sin motivo.
    (
        r"\bexcept\b[^:\n]*:\s*pass\b",
        "Nunca tragues errores: un dato malo es un aviso y una configuración mala un error explícito "
        "(CLAUDE.md regla 1, REQ-NOR-002).",
        r"^src/",
    ),
    # Riesgo 2: fuga de datos de salud. Los logs solo llevan lead_id, perfil y datos técnicos.
    (
        r"\blog(ger|ging)?\.\w+\(.*\b(full_name|email|phone|enquiry_text|nombre|telefono|mensaje|texto)\b",
        "Logs solo con lead_id, perfil y datos técnicos, sin datos personales ni el texto del paciente "
        "(CLAUDE.md regla 2, REQ-NOR-027).",
        r"^src/",
    ),
]
