# Varias sesiones de Claude en paralelo, sin pisarse

Cada sesión trabaja en su propio **worktree** de git: una carpeta con su copia de los archivos y su rama,
que comparte el historial con el repositorio. Dos sesiones nunca editan la misma copia.

## 1. Elige qué tareas pueden ir a la vez
Dos tareas pueden ir en paralelo si sus "Archivos permitidos" no se cruzan. El kit lo calcula:
```bash
python3 evals/alcance.py --solapes            # todas las tareas pendientes
python3 evals/alcance.py --solapes T-004-1 T-004-3
```
```
⚠ T-004-1 y T-004-2 pueden tocar lo mismo: src/cobros/** ↔ src/cobros/recibo.py
Tanda 1 (en paralelo, un worktree por tarea): T-004-1, T-004-3
Tanda 2 (sola): T-004-2
```
Es conservador: ante la duda (un comodín amplio, una tarea sin archivos declarados) las manda en serie.

## 2. Una sesión por tarea, cada una en su worktree
**Con Claude Code** (lo crea en `.claude/worktrees/<nombre>/`, en la rama `worktree-<nombre>`):
```bash
claude --worktree t-004-1        # terminal 1
claude --worktree t-004-3        # terminal 2
```
**A mano**, si quieres la carpeta fuera del repositorio o partir de una rama concreta:
```bash
git worktree add ../proyecto-t-004-3 -b t-004-3-informes && cd ../proyecto-t-004-3 && claude
```
Llama al worktree o a la rama por el ID de la tarea (`t-004-3…`): `alcance.py` la reconoce en el nombre de
la rama aunque no se haya ejecutado `/implementar`.

Dentro de cada sesión, lo de siempre: `/implementar T-004-3`. Cada worktree tiene su propio `.kit/` (tarea
activa, resultados), su `make check` y su PR.

## 3. Lo que comparten (y cómo no pisarse ahí)
| Comparten | Riesgo | Qué hacer |
|---|---|---|
| Base de datos y puertos locales | Dos sesiones migran o siembran la misma BD | En `proyecto.mk`, nombres por carpeta: `DB_NAME ?= app_$(notdir $(CURDIR))`, `PORT ?= …` |
| `.env` y otros archivos ignorados | No existen en un worktree nuevo | `.worktreeinclude` (sintaxis de `.gitignore`) los copia en los worktrees que crea Claude Code; con `git worktree add`, cópialos tú |
| Aprobaciones "no volver a preguntar" | Se guardan en el `settings.local.json` del checkout principal y valen para todos los worktrees | Apruébalas en una sesión pensando en todas |
| El historial de git | Dos PRs que tocan zonas vecinas | Fusiona uno, y el otro se rebasa y vuelve a pasar `make check` en la CI |

## 4. Cómo encajan los guardrails
- Claude Code impide que una sesión de worktree edite el checkout principal.
- En una sesión de worktree, los hooks del kit miden las rutas desde la raíz del worktree (campo `cwd`
  de su entrada), no desde `$CLAUDE_PROJECT_DIR`, que sigue apuntando al checkout principal. Por eso
  `.claude/` del worktree sigue protegido y su `src/` se edita con normalidad, y el gate del hook Stop
  se ejecuta en el worktree.
- `alcance.py` y `secretos.py` ignoran `.claude/worktrees/` del checkout principal: cada worktree se
  comprueba en su propia sesión. El instalador añade `.claude/worktrees/` a `.gitignore`.

## 5. Al terminar
Al salir de una sesión de worktree, Claude Code pregunta si lo conserva cuando tiene cambios. Si lo creaste
a mano: `git worktree remove ../proyecto-t-004-3`. Revisa `git worktree list` de vez en cuando.

Para subagentes que trabajen en paralelo dentro de una sesión: `isolation: worktree` en su cabecera
(`.claude/agents/<nombre>.md`).
