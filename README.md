# Normalizador de leads

Módulo del SaaS de VidasPrime que lleva los leads de cualquier clínica a un **esquema común** solo con
configuración: una clínica nueva entra con su perfil en `config/clinicas/`, sin tocar el código.

El encargo y los exports de ejemplo están en `docs/BRIEF_candidato.md` y `docs/clinica_*_leads.json`; qué
se construye y por qué, en `specs/001-normalizar-por-configuracion/`; cómo está organizado, en
`docs/arquitectura.md`. Solo datos sintéticos: se tratan como datos de salud.

## Estado
Fase 1, en construcción: el avance de cada tarea está en `specs/001-normalizar-por-configuracion/tasks.md`.

## Instalación
Necesita Python 3.13.
```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
```

## Uso
```bash
.venv/bin/python -m normalizador --clinica clinica_a --entrada docs/clinica_a_leads.json --salida salida/clinica_a
```
Escribe en la carpeta de salida:
- `leads.jsonl`: un lead por línea con los 12 campos del esquema común.
- `informe.json`: el informe de la carga.

`salida/` está en `.gitignore`: lo que escribe son datos de salud.

## Calidad
- `make check`: tests, lint (ruff), reglas de capas, cobertura de requisitos, secretos y alcance.
- `make test`: solo los tests.
