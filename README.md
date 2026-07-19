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
│       └── logo-bancolombia.svg  # Isotipo + wordmark oficial
├── challenge/
│   └── parte-a-prueba-senior.pdf # Enunciado original del reto
├── .github/workflows/
│   └── deploy.yml                # CI/CD: verificación + despliegue a Pages
└── README.md
```

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

## Despliegue (CI/CD)

El workflow [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) se ejecuta en cada `push` a `main`:

1. **verify** — comprueba que exista `docs/index.html` y el logo, valida el HTML y las referencias a assets.
2. **build** — empaqueta la carpeta `docs/` como artefacto de Pages.
3. **deploy** — publica en GitHub Pages.

### Habilitar Pages (una sola vez)

En el repositorio → **Settings → Pages → Build and deployment → Source: GitHub Actions**. Tras el primer push a `main`, el sitio queda disponible en la URL de Pages.

---

## Decisiones de arquitectura (resumen)

- **Estrategia:** migración evolutiva *Strangler Fig* por olas, no *big-bang* ni reescritura 1:1.
- **Arquitectura:** modular evolutiva en capas (interfaz / orquestación / capacidades / integración) con puertos y adaptadores; se arranca como *modular monolith* y se extraen microservicios **solo cuando un criterio objetivo lo justifica**.
- **Selección tecnológica:** árbol de decisión (BPM / n8n / Power Platform / microservicio / RPA selectivo), no un estándar único.
- **Resiliencia:** saga con compensación, idempotencia, reintentos con backoff y DLQ.
- **Gobierno:** catálogo versionado y política *reuse-first* con *fitness functions* de duplicación.

El detalle y las alternativas descartadas están en la sección **ADRs** del sitio.

---

## Stack

Sitio estático autocontenido: **HTML + CSS + JavaScript vanilla**, diagramas con **Mermaid**, tipografía Open Sans. Sin build step. Identidad visual alineada a Bancolombia (azul oscuro `#2C2A29`, amarillo `#FDDA24`, fondo blanco).

---

## Autoría

**Diseñado y presentado por [Briyid Catalina Cruz Ostos](https://www.linkedin.com/in/bccruzo/)** — Prueba Técnica A · Bancolombia.

> Documento de candidato para proceso de entrevista. El logo de Bancolombia se usa únicamente como contexto de la propuesta; este no es un sitio oficial de la organización.
