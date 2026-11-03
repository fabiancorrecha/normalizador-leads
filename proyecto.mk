# Lo propio de ESTE proyecto. `instalar.sh --actualizar` nunca toca este archivo.
# El Makefile genérico lo incluye primero, así que estas variables mandan.

# Comando de tests de tu stack (por defecto: $(PY) -m pytest con informe JUnit; $(PY) es el Python de
# .venv/ si existe, si no python3). Ejemplos:
# TEST_CMD = npm test
# TEST_CMD = go test ./...

# Linter y formateador sobre TU código (no sobre las piezas del kit). Entra en `make check`, así que la
# herramienta tiene que estar también en la CI: en Python, ponla en requirements-dev.txt (ci.yml lo
# instala); en Node, en devDependencies. Ejemplos:
# LINT_CMD = $(PY) -m ruff check src tests/unit && $(PY) -m ruff format --check src tests/unit  # Python
# LINT_CMD = npx eslint src && npx prettier --check src                                     # JS/TS
# LINT_CMD = test -z "$$(gofmt -l ./internal ./cmd)" && go vet ./...                        # Go
# LINT_CMD = cargo fmt --check && cargo clippy -- -D warnings                               # Rust
# Este proyecto: ruff sobre todo el código propio. Las piezas del kit quedan fuera con `extend-exclude`
# en pyproject.toml, y lo que ignora git (.venv/, .kit/) también.
LINT_CMD = $(PY) -m ruff check . && $(PY) -m ruff format --check .

# Despliegue (solo lo ejecuta el pipeline). Ejemplos:
# DEPLOY_CMD   = fly deploy --app mi-app-$(ENTORNO)
# SMOKE_CMD    = curl -fsS https://mi-app-$(ENTORNO).fly.dev/salud
# ROLLBACK_CMD = fly releases rollback --app mi-app-$(ENTORNO)

# Objetivos propios. Decláralos en .PHONY: si se llaman como una carpeta (db/, docs/…),
# make los da por hechos y no los ejecuta, sin avisar.
# .PHONY: db
# db:
# 	@bash scripts/dev_db.sh
