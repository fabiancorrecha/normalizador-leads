## Qué y por qué
<!-- Tarea (T-NNN-N) y spec. Una frase de por qué ahora. -->

## Requisitos cubiertos
<!-- REQ-XXX-NNN → test que lo demuestra. -->

## Cómo se ha verificado
<!-- Salida de `make check` (y de `make eval-ia` si cambia un prompt). "Funciona en mi máquina" no vale. -->

## Riesgos y vuelta atrás
<!-- Qué podría romperse en producción y cómo se deshace (feature flag, ROLLBACK_CMD, migración reversible). -->

## Comprobaciones
- [ ] Cada test nuevo cita su requisito y lo vi fallar antes de implementar.
- [ ] Solo toca los archivos permitidos de la tarea (`make alcance`).
- [ ] Sin secretos ni datos personales reales (`make secretos`).
- [ ] Diagrama actualizado si cambia la arquitectura o un flujo; ADR si la decisión es difícil de revertir.
- [ ] Migraciones *expand/contract* y funcionalidad nueva tras un feature flag apagado.
- [ ] Si lo escribió un agente: lo he leído entero y entiendo cada línea.
