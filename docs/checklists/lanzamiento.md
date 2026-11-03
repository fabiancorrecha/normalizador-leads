# Checklist de lanzamiento

Regla de oro: **Claude prepara el cambio; el pipeline lo despliega; una persona lo aprueba.**
El hook `guard_bash.py` bloquea los comandos de despliegue para el agente a propósito.
`/lanzamiento <spec>` recorre esta checklist con evidencia y deja el resultado en `docs/lanzamientos/`.

## Antes
- [ ] `make check` y `make seguridad` en verde en CI; revisión del subagente y de una persona.
- [ ] ADRs de las decisiones nuevas en estado Aceptada.
- [ ] **Migraciones compatibles hacia atrás** (*expand / contract*): primero se añade, se despliega,
      se migran datos y solo después se elimina lo viejo. Nunca renombrar o borrar en el mismo paso.
- [ ] Funcionalidad nueva detrás de un **feature flag**, apagado por defecto.
- [ ] **Plan de vuelta atrás** escrito y probado en staging (`make rollback ENTORNO=staging`).
- [ ] Observabilidad lista (`docs/checklists/observabilidad.md`): panel, alertas del flujo nuevo y un runbook
      por alerta (`docs/plantillas/runbook.md`).
- [ ] Requisitos no funcionales verificados contra staging: `make carga` y `make e2e` con `BASE_URL`.
- [ ] Criterios de vuelta atrás definidos **antes**: p. ej. errores > 1%, p95 > 2× lo normal,
      cualquier incidente de seguridad o de datos.
- [ ] Comunicación preparada (soporte, clientes piloto, notas de versión).

## Durante (lo hace el pipeline `.github/workflows/deploy.yml`)
1. Verificación (`make check`) → despliegue a **staging** → pruebas de humo (`make smoke`).
2. **Aprobación humana** (entorno `produccion` en GitHub con revisores obligatorios).
3. Despliegue a **producción** → pruebas de humo → vuelta atrás automática si fallan.
4. Activación gradual del flag: clientes piloto → 10% → 50% → 100%, vigilando el panel en cada paso.

## Después
- [ ] Comprobar la **métrica de éxito** de la spec con datos reales (días o semanas, no minutos).
- [ ] Retirar el feature flag cuando esté al 100% y estable.
- [ ] Retrospectiva corta: cada problema se convierte en un test, una regla de `CLAUDE.md` o un caso de eval.
      Si hubo incidente: postmortem sin culpables (`docs/plantillas/postmortem.md`).

## Configuración única
- En `proyecto.mk`: `DEPLOY_CMD`, `SMOKE_CMD` y `ROLLBACK_CMD` con los comandos de tu plataforma.
- En GitHub, `Settings → Environments`: crea `staging` y `produccion`; en `produccion` activa **Required reviewers**.
  Los secretos de despliegue van en cada entorno, nunca en el repositorio.
- En GitHub, `Settings → Secrets and variables → Actions → Variables`: crea `DESPLIEGUE_ACTIVO=true`.
  Hasta entonces `deploy.yml` no se ejecuta (así no falla en cada push mientras no esté configurado).
