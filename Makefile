# Genérico del kit: `instalar.sh --actualizar` lo reemplaza.
# Lo propio de tu proyecto (TEST_CMD, DEPLOY_CMD, arrancar la BD…) va en proyecto.mk, que nunca se toca.
# Se incluye primero para que sus variables manden sobre los valores por defecto de abajo.
-include proyecto.mk
.DEFAULT_GOAL := check

# Python del proyecto: el de .venv/ si existe (aunque no esté activado); si no, python3. Así make check
# funciona igual desde una terminal, desde el hook Stop de Claude Code o desde el editor. En macOS con el
# Python de Homebrew, `pip install` fuera de un entorno está bloqueado (PEP 668): pytest va en .venv/.
# En proyecto.mk, llama a las herramientas de Python con $(PY): `$(PY) -m ruff …`, `$(PY) -m uvicorn …`.
# (El PATH exportado solo lo respetan los comandos que pasan por la shell: el make 3.81 de macOS busca
# los comandos simples con el PATH original. Por eso el kit usa $(PY) y no confía en el PATH.)
ifneq ($(wildcard .venv/bin/python),)
PY ?= .venv/bin/python
export PATH := $(CURDIR)/.venv/bin:$(PATH)
else
PY ?= python3
endif

# Informe JUnit de los tests: con él, la cobertura solo cuenta los tests que pasan. Si tu TEST_CMD
# (en proyecto.mk) no lo genera, la cobertura vuelve a contar menciones y lo avisa.
JUNIT ?= .kit/resultados/junit.xml
TEST_CMD ?= $(PY) -m pytest -q --junitxml=$(JUNIT)
ENTORNO ?= staging

.PHONY: check test lint arquitectura guardrails coverage secretos alcance seguridad hooks-git carga e2e mapa \
        eval-ia eval-juez eval-agente deploy smoke rollback

# Gate completo: lo ejecutan el hook Stop de Claude Code y la CI.
check: test lint arquitectura coverage secretos alcance
ifeq ($(findstring pytest,$(TEST_CMD)),)
check: guardrails
endif

test:
	@rm -f $(JUNIT)
	@$(TEST_CMD)

# Estilo y errores comunes con el linter y el formateador del stack (LINT_CMD en proyecto.mk).
lint:
ifeq ($(strip $(LINT_CMD)),)
	@echo "Lint: sin LINT_CMD en proyecto.mk (recomendado: el linter y el formateador de tu stack)."
else
	@$(LINT_CMD)
endif

# Reglas de dependencia entre capas de docs/arquitectura.md.
arquitectura:
	@$(PY) evals/arquitectura.py

guardrails:
	@$(PY) -m pytest -q tests/test_guardrails.py tests/test_reglas_proyecto.py tests/test_kit.py

# Mapa del código con graphify (opcional): solo análisis del código, local, sin IA y gratis. Claude lo
# consulta (`graphify explain|affected|path|query`) en vez de leer archivos enteros. Qué queda fuera:
# .graphifyignore. Versión fijada con el mismo enfriamiento que las dependencias (7 días): súbela a propósito.
GRAPHIFY_VERSION ?= 0.9.93
mapa:
	@if ! command -v graphify >/dev/null 2>&1; then \
	  echo "Mapa: graphify no está instalado (es opcional). Para usarlo: uv tool install graphifyy==$(GRAPHIFY_VERSION)"; \
	else \
	  version=$$(graphify --version 2>/dev/null | awk '{print $$NF}'); \
	  [ "$$version" = "$(GRAPHIFY_VERSION)" ] || echo "Aviso: tienes graphify $$version; el kit está probado con $(GRAPHIFY_VERSION)."; \
	  GRAPHIFY_BACKEND=none graphify update .; \
	fi

coverage:
	@$(PY) evals/spec_coverage.py $(if $(wildcard $(JUNIT)),--junit $(JUNIT),)

# Solo hay tarea activa tras /implementar (o en una rama t-NNN-N-…): sin ella no comprueba nada.
alcance:
	@$(PY) evals/alcance.py

secretos:
	@$(PY) evals/secretos.py

# Secretos + dependencias con vulnerabilidades conocidas (necesita red: se ejecuta en CI).
seguridad: secretos
	@$(PY) evals/dependencias.py

# Para las personas del equipo (una vez por clon): el commit se para en tu máquina si lleva un secreto,
# con los mismos patrones que el hook del agente.
HOOK_GIT = $(shell git rev-parse --git-path hooks 2>/dev/null)/pre-commit
hooks-git:
	@git rev-parse --git-dir >/dev/null 2>&1 || { echo "No es un repositorio git."; exit 1; }
	@if [ -e "$(HOOK_GIT)" ] && ! grep -q "secretos.py --preparados" "$(HOOK_GIT)"; then \
	  echo "Ya tienes un pre-commit ($(HOOK_GIT)): añádele la línea  python3 evals/secretos.py --preparados"; exit 1; fi
	@mkdir -p "$(dir $(HOOK_GIT))"
	@printf '#!/bin/sh\n# Instalado por make hooks-git: para el commit si lo preparado lleva un secreto.\nexec python3 evals/secretos.py --preparados\n' > "$(HOOK_GIT)"
	@chmod +x "$(HOOK_GIT)"
	@echo "✅ pre-commit instalado: cada commit pasa por evals/secretos.py --preparados"

# ── Requisitos no funcionales: necesitan la aplicación arrancada en URL_ENTORNO (local o staging) ──
# Dentro de check se saltan y la cobertura los muestra como "se verifica en entorno"; deploy.yml los
# ejecuta contra staging si activas NFR_ACTIVOS. Carga: k6. Interfaz y accesibilidad: Playwright + axe-core.
carga e2e:
	@test -n "$(URL_ENTORNO)" || { echo "Uso: make $@ URL_ENTORNO=https://staging.ejemplo.com"; exit 1; }
	@URL_ENTORNO=$(URL_ENTORNO) $(PY) -m pytest -q tests/$@

# ── Evals de IA (prompts/README.md). Llaman al modelo y cuestan dinero: a mano o en la CI cuando
# cambia un prompt, nunca dentro de check. SIMULADO=prompts/<f>/simulado prueba el circuito gratis.
#   make eval-ia   PROMPT=prompts/<f>/vN.md [BASE=prompts/<f>/vN-1.md] [REPETICIONES=3]
#   make eval-juez PROMPT=prompts/<f>/vN.md [CALIBRAR=prompts/<f>/humanas.jsonl]
REPETICIONES ?= 3
IA_SIMULADO = $(if $(SIMULADO),--simulado $(SIMULADO),)

eval-ia:
ifeq ($(strip $(PROMPT)),)
	@echo "Uso: make eval-ia PROMPT=prompts/<funcionalidad>/vN.md [BASE=prompts/<funcionalidad>/vN-1.md] [REPETICIONES=3]" && exit 1
else
	@$(PY) evals/ia/generar.py $(PROMPT) --repeticiones $(REPETICIONES) $(IA_SIMULADO)
ifneq ($(strip $(BASE)),)
	@$(PY) evals/ia/generar.py $(BASE) --repeticiones $(REPETICIONES) --reutilizar $(IA_SIMULADO)
endif
	@$(PY) evals/ia/evaluar.py $(PROMPT) $(if $(strip $(BASE)),--base $(BASE),)
endif

eval-juez:
ifeq ($(strip $(PROMPT)),)
	@echo "Uso: make eval-juez PROMPT=prompts/<funcionalidad>/vN.md [CALIBRAR=prompts/<funcionalidad>/humanas.jsonl]" && exit 1
else
	@$(PY) evals/ia/juez.py $(PROMPT) --reutilizar $(IA_SIMULADO) $(if $(strip $(CALIBRAR)),--calibrar $(CALIBRAR),)
endif

# Caro y no determinista: solo al cambiar CLAUDE.md, .claude/ o el modelo.
eval-agente:
	@$(PY) evals/agente/run.py --intentos 3

# ── Despliegue: solo lo ejecuta el pipeline (.github/workflows/deploy.yml), nunca el agente ──
# Define DEPLOY_CMD, SMOKE_CMD y ROLLBACK_CMD en proyecto.mk con los comandos de tu plataforma.
deploy:
ifeq ($(strip $(DEPLOY_CMD)),)
	@echo "Define DEPLOY_CMD en proyecto.mk para tu plataforma (ENTORNO=$(ENTORNO))." && exit 1
else
	$(DEPLOY_CMD)
endif

smoke:
ifeq ($(strip $(SMOKE_CMD)),)
	@echo "Define SMOKE_CMD en proyecto.mk: 3-5 peticiones a los flujos críticos de $(ENTORNO)." && exit 1
else
	$(SMOKE_CMD)
endif

rollback:
ifeq ($(strip $(ROLLBACK_CMD)),)
	@echo "Define ROLLBACK_CMD en proyecto.mk: vuelve a desplegar la versión anterior en $(ENTORNO)." && exit 1
else
	$(ROLLBACK_CMD)
endif
