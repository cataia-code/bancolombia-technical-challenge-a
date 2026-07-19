# Discovery Ola 0 — inventario, scoring, clustering y catálogo

Prueba de concepto **ejecutable localmente** que materializa el discovery de la
**Ola 0** de la propuesta (Preguntas 1 y 2): toma un inventario de taskbots —la
metadata que se exporta del **Control Room de Automation Anywhere**— y produce el
**catálogo de capacidades** con el que se decide qué **migrar / consolidar / retirar**,
la **matriz API / no-API** y el **baseline de reducción**.

Convierte en **evidencia ejecutable** lo que en el sitio se explica de forma
conceptual: no hay números inventados, salen de correr el motor sobre datos.

> **Cero dependencias** en tiempo de ejecución: el motor usa solo la librería
> estándar de Python. `pytest` es únicamente para las pruebas.

## Qué demuestra

| Paso del discovery | Dónde se ve |
| --- | --- |
| **Normalización** — cada taskbot se reduce a una *firma* (pasos ∪ sistemas) | `Taskbot.signature` / `test_signature_includes_steps_and_prefixed_systems` |
| **Similitud** — clustering por Jaccard sobre firmas (single-linkage) | `cluster_taskbots` / `test_groups_exact_duplicates_into_the_same_cluster` |
| **Scoring** — score compuesto con la **misma fórmula del sitio** (P2) | `priority_score` / `test_lower_complexity_yields_a_higher_score` |
| **Decisión** — migrar / consolidar / retirar por cluster | `decide_capability` / `test_marks_exactly_one_bot_to_migrate_per_cluster` |
| **Matriz API / no-API** — sistemas destino y bots bloqueados | `api_matrix` / `test_api_matrix_detects_systems_without_api` |
| **Salida Ola 0** — catálogo + baseline de reducción | `run_discovery` / `test_catalog_reports_a_consistent_summary` |

## Fórmula de scoring (idéntica a la Pregunta 2 del sitio)

```
Score = 0.30·Valor + 0.25·Consolidación + 0.20·(6−Complejidad)
      + 0.15·(6−Riesgo) + 0.10·(6−Dependencia)
```

- **Valor** se deriva de `volumen × criticidad` (bandas 1–5).
- **Consolidación** crece con el tamaño del cluster (migrar el bot que colapsa 6
  duplicados rinde más que migrar el bot "estrella" aislado).
- Complejidad, riesgo y dependencia se **invierten**: menor es mejor.

## Clustering — la decisión de negocio clave

Dos taskbots se agrupan si su **Jaccard** sobre la firma (pasos ∪ sistemas) supera
`JACCARD_THRESHOLD`, y **solo** si tocan el mismo sistema destino.

- **Umbral alto** (p.ej. `0.85`) = conservador: no consolida por coincidencia superficial.
- **Umbral bajo** (p.ej. `0.55`) = agresivo: más consolidación, más riesgo de falso positivo.

Con `0.75` (por defecto) se evita el *chaining* de single-linkage entre capacidades
vecinas (p.ej. onboarding vs. desembolso, que comparten pasos pero **no** son lo mismo).
Los clusters son **candidatos**: la Ola 0 los valida con los dueños de proceso antes
de consolidar. El umbral se calibra en taller y queda registrado en un ADR.

## Cómo ejecutarlo

```bash
# PowerShell desde la raíz del repo
.\.venv\Scripts\Activate.ps1
cd discovery
python discovery.py                 # imprime el catálogo y lo escribe en out/
python -m pytest tests/ -q          # 22 tests
```

Genera en [`out/`](out/):

- `wave0_catalog.json` — catálogo completo (capacidades, decisiones, matriz API).
- `wave0_catalog.md` — resumen legible.

## Salida sobre el inventario de ejemplo (44 taskbots)

| Métrica | Valor |
| --- | --- |
| Taskbots inventariados | **44** |
| Capacidades reales (clusters) | **15** |
| Reducción estimada | **65.9%** (umbral Jaccard = 0.75) |
| Decisiones | MIGRAR 10 · CONSOLIDAR 29 · RETIRAR 5 |
| Bloqueados por API faltante | **5** capacidades (SIFIN, PortalSFC, PortalWeb…) |

La matriz API muestra que el mayor volumen (SIFIN, 41.200 ejec./mes) **no tiene API**:
exponerla es ruta crítica del programa, no un detalle de implementación. El
`sample_inventory.csv` incluye duplicados regionales, variantes por segmento/producto
y bots obsoletos de bajo valor, para que consolidación, retiro y matriz sean visibles.

## Estructura

```text
discovery/
├── discovery.py            # motor: normalización, clustering, scoring, decisión, matriz
├── sample_inventory.csv    # inventario de ejemplo (metadata estilo Control Room)
├── tests/
│   └── test_discovery.py   # 22 tests
├── out/                    # catálogo generado (JSON + Markdown)
└── requirements.txt        # solo pytest (el motor no tiene dependencias)
```
