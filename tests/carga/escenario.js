// Prueba de carga del flujo crítico con k6. La lanza tests/carga/test_carga.py (`make carga`) contra
// URL_ENTORNO. Ajusta ruta, usuarios, duración y umbrales con variables de entorno desde el test, para
// que cada requisito no funcional (REQ-…) tenga su test con sus cifras.
import http from 'k6/http';
import { check, sleep } from 'k6';

const URL = `${__ENV.URL_ENTORNO}${__ENV.RUTA || '/'}`;
const USUARIOS = Number(__ENV.USUARIOS || 20);

export const options = {
  scenarios: {
    flujo_critico: {
      executor: 'ramping-vus',
      stages: [
        { duration: __ENV.SUBIDA || '10s', target: USUARIOS },
        { duration: __ENV.DURACION || '30s', target: USUARIOS },
        { duration: '5s', target: 0 },
      ],
    },
  },
  // Si un umbral no se cumple, k6 termina con error y el test falla.
  thresholds: {
    http_req_duration: [`p(95)<${Number(__ENV.P95_MS || 300)}`],
    http_req_failed: [`rate<${Number(__ENV.ERRORES_MAX || 0.01)}`],
    checks: ['rate>0.99'],
  },
};

export default function () {
  const respuesta = http.get(URL);
  check(respuesta, { 'responde 2xx': (r) => r.status >= 200 && r.status < 300 });
  sleep(1);
}
