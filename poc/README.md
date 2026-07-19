# PoC — Orquestación con saga, resiliencia y trazabilidad

Prueba de concepto **ejecutable localmente** que materializa el patrón técnico de la propuesta (Pregunta 12): un proceso orquestado como **saga** con **validación, ejecución idempotente, reintentos con backoff, compensación (rollback), dead-letter queue y trazabilidad por `correlationId`**.

Está diseñada con **puertos y adaptadores** (igual que la arquitectura propuesta): el motor no conoce Redis ni HTTP; corre con fakes en memoria (tests) o con Redis + API mock (docker-compose) sin cambiar una línea.

## Qué demuestra

| Comportamiento | Dónde se ve |
| --- | --- |
| Caso exitoso (entrada → validación → ejecución → salida) | `demo.py` esc. 1 / `test_flujo_pago_exitoso` |
| Reintento ante fallo **transitorio** (backoff + jitter) | `demo.py` esc. 2 / `test_reintento_transitorio_luego_exito` |
| Error **permanente** → no se reintenta → **DLQ** | `test_error_permanente...`, `test_reintentos_agotados_van_a_dlq` |
| **Compensación** (rollback en orden inverso) | `demo.py` esc. 3 / `test_flujo_falla_tardia_compensa_el_pago` |
| **Idempotencia** (no re-aplica efectos en reprocesos) | `test_idempotencia_evita_doble_efecto` |
| **Trazabilidad** por `correlationId` (logs estructurados) | eventos INICIO/EJECUCION/REINTENTO/COMPENSACION/DLQ/SALIDA |

## Estructura

```text
poc/
├── src/
│   ├── saga/            # Motor: engine, models, ports, errors (sin dependencias externas)
│   ├── components/      # Capacidades reutilizables: validación, notificación
│   ├── adapters/        # ApiAdapter (HTTP) y RpaAdapter (mock UI) — mismo puerto
│   ├── infra/           # Fakes en memoria + implementaciones Redis + logging
│   └── app/             # FastAPI: orchestrator (webhook) y mock_api (sistema destino)
├── tests/               # 9 tests (motor + flujo), sin infraestructura
├── demo.py              # Demo sin infra: imprime la traza de 3 escenarios
├── docker-compose.yml   # orquestador + mock-api + redis
├── Dockerfile
└── requirements.txt
```

## Ejecutar

### 1) Tests (rápido, sin dependencias externas)

```bash
cd poc
python -m pytest tests/ -q
```

### 2) Demo de trazas (sin infraestructura)

```bash
cd poc
python demo.py
```

Imprime la traza JSON por `correlationId` del caso exitoso, del reintento transitorio y del error permanente con compensación + DLQ.

### 3) Stack completo (docker-compose)

```bash
cd poc
docker compose up --build
```

En otra terminal:

```bash
# Caso exitoso
curl -s localhost:8000/webhook -H "content-type: application/json" \
  -d '{"cuenta":"123","monto":100000,"modo":"ok"}' | jq

# Fallo transitorio -> reintenta y termina OK
curl -s localhost:8000/webhook -H "content-type: application/json" \
  -d '{"cuenta":"123","monto":100000,"modo":"transitorio"}' | jq

# Rechazo permanente -> compensación + DLQ
curl -s localhost:8000/webhook -H "content-type: application/json" \
  -d '{"cuenta":"123","monto":100000,"modo":"permanente"}' | jq

# Inspeccionar la DLQ
curl -s localhost:8000/dlq | jq
```

La respuesta incluye `correlationId`, `status`, `deadLettered`, `compensados` y la `trace` completa. Los logs estructurados salen por `stderr` de cada servicio.

## Decisiones de diseño

- **Transitorio vs permanente** es la distinción central: solo lo transitorio se reintenta; lo permanente compensa y va a DLQ de inmediato.
- **Idempotencia** por `(correlationId, paso)`: ante un reproceso desde la cola, los efectos no se duplican.
- **Compensación** en orden inverso porque en sistemas distribuidos no hay transacción ACID global (patrón saga).
- **Puertos y adaptadores**: el motor es agnóstico de infraestructura → alta testabilidad y portabilidad (mismo código con Redis o en memoria).

## Alcance

Es una PoC de **patrón**, no un producto: sin auth real, persistencia mínima (Redis) y un solo proceso de ejemplo. La propuesta describe cómo se llevaría a producción (event store, OpenAPI/AsyncAPI, vault, OTel, dashboards, RBAC, etc.).
