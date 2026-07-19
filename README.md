# Prueba Técnica A · Bancolombia — Evolución de RPA

Propuesta técnica para la **Parte A** del reto de Senior Software Engineer: cómo evolucionar una operación de automatización de **500 RPAs / 12.000 taskbots sobre Automation Anywhere** hacia una **arquitectura modular evolutiva, reutilizable y con menor deuda técnica**, retirando la plataforma RPA como *core* antes de diciembre de 2027.

El entregable es un **sitio web técnico navegable** que responde las 20 preguntas del reto (5 bloques) con criterio de arquitectura, diagramas UML, ADRs y una revisión crítica.

> **Sitio publicado:** una vez habilitado GitHub Pages → `https://cataia-code.github.io/bancolombia-technical-challenge-a/`

---

## Problema que resuelve

Desmontar una dependencia de plataforma RPA **sin detener la operación** y **sin heredar la fragmentación** actual (alta redundancia de tareas, utilidades y variantes; fuerte dependencia de automatización por interfaz gráfica). La propuesta se apoya en tres decisiones nucleares:

1. **Racionalizar antes de migrar** — de 12.000 taskbots a un catálogo real de capacidades (consolidar/retirar, no migrar todo).
2. **Orquestar, no bot-izar** — orquestación (BPM/n8n) coordinando componentes reutilizables; RPA como adaptador de borde solo donde no hay API.
3. **Gobierno desde el diseño** — catálogo versionado, trazabilidad end-to-end por `correlationId`, seguridad y observabilidad como plataforma.

---

## Contenido del sitio

| Sección | Qué incluye |
| --- | --- |
| Resumen & Requisitos | Entendimiento, requisitos funcionales/no funcionales, supuestos y preguntas abiertas |
| Bloques A–E | Las 20 respuestas del reto con trade-offs explícitos |
| Galería UML | Contexto (C4), componentes, casos de uso, secuencia, actividad de resiliencia y roadmap de olas |
| ADRs | 6 Architecture Decision Records |
| Revisión crítica | Autoevaluación honesta y calificación |

Cada diagrama es interactivo: **zoom/pan** a pantalla completa y **descarga en SVG/PNG**.

---

## Estructura del proyecto

```text
.
├── docs/                         # Sitio estático (fuente de GitHub Pages)
│   ├── index.html                # Aplicación de una sola página (SPA) autocontenida
│   └── assets/
│       ├── images/               # Logos Bancolombia (svg wordmark + png isotipo/favicon)
│       └── vendor/               # Mermaid empaquetado localmente (sin CDN)
├── discovery/                    # Discovery Ola 0 ejecutable: scoring, clustering, catálogo
│   ├── discovery.py              # motor: normalización, similitud, scoring, decisión, matriz API
│   ├── sample_inventory.csv      # inventario de ejemplo (metadata estilo Control Room)
│   ├── tests/                    # 22 tests del motor de discovery
│   └── out/                      # catálogo Ola 0 generado (JSON + Markdown)
├── poc/                          # PoC ejecutable: saga, reintentos, DLQ, compensación
│   ├── src/                      # motor, componentes, adaptadores, infra, app (FastAPI)
│   ├── tests/                    # 38 tests con 100% coverage sobre poc/src
│   ├── contracts/                # OpenAPI, AsyncAPI y manifiesto de componente
│   ├── demo.py                   # demo de trazas sin infraestructura
│   └── docker-compose.yml        # orquestador + mock-api + redis
├── challenge/
│   └── parte-a-prueba-senior.pdf # Enunciado original del reto
├── .github/workflows/
│   └── deploy.yml                # CI/CD: verificación + despliegue a Pages
└── README.md
```

## PoC ejecutable (`/poc`)

Materializa el patrón técnico de la propuesta (Pregunta 12): saga con **reintentos + backoff**, **compensación** (rollback), **DLQ**, **idempotencia** y **trazabilidad por `correlationId`**. Diseñada con puertos y adaptadores.

```bash
# PowerShell from the repo root
.\.venv\Scripts\Activate.ps1
cd poc
python -m pytest tests/ --cov=src --cov-report=term-missing --cov-fail-under=100
python demo.py                 # traza de 3 escenarios sin infraestructura
docker compose up --build      # stack completo: orquestador + mock-api + redis
```

Ver [`poc/README.md`](poc/README.md) para el detalle y los `curl` de ejemplo. Los contratos de referencia están en [`poc/contracts/`](poc/contracts/): API síncrona, eventos asíncronos y manifiesto de componente versionado.

## Discovery Ola 0 ejecutable (`/discovery`)

Materializa el discovery de la **Ola 0** (Preguntas 1 y 2): toma un inventario de taskbots (metadata estilo Control Room de Automation Anywhere) y produce el **catálogo de capacidades** — normalización a *firmas*, **clustering** por similitud (Jaccard), **scoring** con la misma fórmula del sitio, decisión **migrar/consolidar/retirar** y **matriz API / no-API**. Cero dependencias: solo librería estándar.

```bash
# PowerShell desde la raíz del repo
.\.venv\Scripts\Activate.ps1
cd discovery
python discovery.py                 # imprime el catálogo y lo escribe en out/
python -m pytest tests/ -q          # 22 tests
```

Sobre el inventario de ejemplo (44 taskbots) el motor colapsa a **15 capacidades (65.9% de reducción)**, marca **5 capacidades bloqueadas por API faltante** y prioriza el backlog por score. Ver [`discovery/README.md`](discovery/README.md).

---

## Cómo verlo en local

El sitio es estático; requiere un servidor HTTP simple (Mermaid no renderiza al abrir el archivo con `file://`).

```bash
# Opción 1 — Python
cd docs
python -m http.server 8080
# abrir http://localhost:8080

# Opción 2 — Node
npx serve docs
```

---

## Despliegue

El workflow [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) publica `docs/` en GitHub Pages después de verificar el sitio y correr la PoC. La concurrencia cancela despliegues anteriores en curso y, al terminar, limpia deployments históricos para conservar solo el último de `github-pages`.

Validaciones principales:

- estructura y referencias locales de `docs/`
- HTML sin errores estructurales graves
- tests de la PoC con 100% de coverage sobre `poc/src`
- `docker compose config` de la PoC

---

## Decisiones de arquitectura (resumen)

- **Estrategia:** migración evolutiva *Strangler Fig* por olas, no *big-bang* ni reescritura 1:1.
- **Arquitectura:** modular evolutiva en capas (interfaz / orquestación / capacidades / integración) con puertos y adaptadores; se arranca como *modular monolith* y se extraen microservicios **solo cuando un criterio objetivo lo justifica**.
- **Selección tecnológica:** árbol de decisión (BPM / n8n / Power Platform / microservicio / RPA selectivo), no un estándar único.
- **Resiliencia:** saga con compensación, idempotencia, reintentos con backoff y DLQ.
- **Gobierno:** catálogo versionado y política *reuse-first* con *fitness functions* de duplicación.

El detalle y las alternativas descartadas están en la sección **ADRs** del sitio.

---

## Autoría

**Diseñado y presentado por [Briyid Catalina Cruz Ostos](https://www.linkedin.com/in/bccruzo/)** — Prueba Técnica A · Bancolombia.

> Documento de candidato para proceso de entrevista. El logo de Bancolombia se usa únicamente como contexto de la propuesta; este no es un sitio oficial de la organización.
