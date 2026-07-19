"""Wave 0 discovery / rationalization engine.

Takes the taskbot inventory (metadata exportable from the Automation Anywhere
Control Room) and produces EXACTLY the Wave 0 output described on the site
(Question 1 and Question 2):

  1. Normalization -> every taskbot is reduced to a "signature" (steps + systems).
  2. Similarity    -> clustering by Jaccard over signatures (single-linkage).
  3. Scoring       -> composite score using the SAME formula documented on the site.
  4. Decision      -> migrate / consolidate / retire per cluster.
  5. API matrix    -> target systems with/without API and bots blocked by it.
  6. Wave 0 catalog-> JSON + human-readable summary.

No external dependencies: standard library only. Run it with

    python discovery.py

which writes the catalog to discovery/out/.
"""
from __future__ import annotations

import csv
import json
import os
from dataclasses import asdict, dataclass, field
from itertools import combinations

# ---------------------------------------------------------------------------
# Tunable parameters (fixed in an architecture workshop and recorded in an ADR)
# ---------------------------------------------------------------------------

# Similarity threshold to treat two taskbots as "the same capability".
# High (e.g. 0.85) = conservative: does not consolidate on shallow overlap.
# Low  (e.g. 0.55) = aggressive: more consolidation, higher false-positive risk.
# This is the key business decision of the clustering step (see Q1, human review).
# At 0.75 single-linkage "chaining" between neighbouring capabilities is avoided
# (e.g. onboarding vs disbursement, which share steps but are not the same thing).
JACCARD_THRESHOLD = 0.75

# Composite-score weights (site, Question 2). They add up to 1.0.
WEIGHTS = {
    "value": 0.30,
    "consolidation": 0.25,
    "complexity": 0.20,   # inverted: (6 - complexity)
    "risk": 0.15,         # inverted: (6 - risk)
    "dependency": 0.10,   # inverted: (6 - dependency)
}

# A cluster whose best bot does not reach this value is considered obsolete -> retire.
MIN_VALUE_TO_MIGRATE = 3

# Decision labels (internal, English). render_markdown maps them to Spanish for display.
MIGRATE = "MIGRATE"
CONSOLIDATE = "CONSOLIDATE"
RETIRE = "RETIRE"


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

@dataclass
class Taskbot:
    bot_id: str
    name: str
    region: str
    target_system: str
    has_api: bool
    monthly_volume: int
    criticality: int     # 1-5
    complexity: int      # 1-5
    risk: int            # 1-5
    dependency: int      # 1-5
    steps: list[str]
    systems: list[str]

    @property
    def signature(self) -> set[str]:
        """Canonical signature: steps + (prefixed) systems as a single set."""
        return set(self.steps) | {f"sys:{s}" for s in self.systems}


def load_inventory(path: str) -> list[Taskbot]:
    bots: list[Taskbot] = []
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            bots.append(Taskbot(
                bot_id=row["bot_id"],
                name=row["name"],
                region=row["region"],
                target_system=row["target_system"],
                has_api=row["has_api"].strip().lower() == "true",
                monthly_volume=int(row["monthly_volume"]),
                criticality=int(row["criticality"]),
                complexity=int(row["complexity"]),
                risk=int(row["risk"]),
                dependency=int(row["dependency"]),
                steps=[s for s in row["steps"].split("|") if s],
                systems=[s for s in row["systems"].split("|") if s],
            ))
    return bots


# ---------------------------------------------------------------------------
# 2 - Similarity and clustering
# ---------------------------------------------------------------------------

def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def cluster_taskbots(bots: list[Taskbot], threshold: float = JACCARD_THRESHOLD) -> list[list[Taskbot]]:
    """Single-linkage: two bots share a cluster if their Jaccard >= threshold.

    Resolved as connected components with union-find (no dependencies). Only bots
    hitting the SAME target system are joined: two look-alike flows that touch
    different systems are not the same capability.
    """
    index = {b.bot_id: i for i, b in enumerate(bots)}
    parent = list(range(len(bots)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        parent[find(x)] = find(y)

    for a, b in combinations(bots, 2):
        if a.target_system != b.target_system:
            continue
        if jaccard(a.signature, b.signature) >= threshold:
            union(index[a.bot_id], index[b.bot_id])

    groups: dict[int, list[Taskbot]] = {}
    for b in bots:
        groups.setdefault(find(index[b.bot_id]), []).append(b)
    # stable order: by size desc, then by representative id
    return sorted(groups.values(), key=lambda g: (-len(g), g[0].bot_id))


# ---------------------------------------------------------------------------
# 3 - Scoring (formula identical to the site, Question 2)
# ---------------------------------------------------------------------------

def business_value_factor(bot: Taskbot) -> float:
    """Business value 1-5 from volume x criticality (log-banded volume)."""
    v = bot.monthly_volume
    volume_score = 1 if v < 200 else 2 if v < 1000 else 3 if v < 2500 else 4 if v < 5000 else 5
    return round((volume_score + bot.criticality) / 2, 2)


def consolidation_factor(cluster_size: int) -> int:
    """How many bots collapse into one component. More bots = more value in consolidating."""
    return 1 if cluster_size <= 1 else 2 if cluster_size == 2 else 3 if cluster_size <= 4 else 4 if cluster_size <= 6 else 5


def priority_score(bot: Taskbot, cluster_size: int) -> float:
    value = business_value_factor(bot)
    consolidation = consolidation_factor(cluster_size)
    s = (
        WEIGHTS["value"] * value
        + WEIGHTS["consolidation"] * consolidation
        + WEIGHTS["complexity"] * (6 - bot.complexity)
        + WEIGHTS["risk"] * (6 - bot.risk)
        + WEIGHTS["dependency"] * (6 - bot.dependency)
    )
    return round(s, 2)


# ---------------------------------------------------------------------------
# 4 - Per-cluster decision (migrate / consolidate / retire)
# ---------------------------------------------------------------------------

@dataclass
class Capability:
    capability_id: str
    target_system: str
    has_api: bool
    taskbots: list[str]
    canonical: str
    cluster_decision: str            # MIGRATE | RETIRE
    max_value: float
    canonical_score: float
    blocked_by_api: bool
    bot_decisions: dict = field(default_factory=dict)  # bot_id -> MIGRATE/CONSOLIDATE/RETIRE


def decide_capability(cluster: list[Taskbot]) -> Capability:
    size = len(cluster)
    # canonical: best score within the cluster (best base to migrate/keep)
    canonical = max(cluster, key=lambda b: priority_score(b, size))
    max_value = max(business_value_factor(b) for b in cluster)

    if max_value < MIN_VALUE_TO_MIGRATE:
        cluster_decision = RETIRE
        bot_decisions = {b.bot_id: RETIRE for b in cluster}
    else:
        cluster_decision = MIGRATE
        bot_decisions = {
            b.bot_id: (MIGRATE if b.bot_id == canonical.bot_id else CONSOLIDATE)
            for b in cluster
        }

    blocked = cluster_decision == MIGRATE and not canonical.has_api

    return Capability(
        capability_id=f"CAP-{canonical.bot_id}",
        target_system=canonical.target_system,
        has_api=canonical.has_api,
        taskbots=[b.bot_id for b in cluster],
        canonical=canonical.bot_id,
        cluster_decision=cluster_decision,
        max_value=max_value,
        canonical_score=priority_score(canonical, size),
        blocked_by_api=blocked,
        bot_decisions=bot_decisions,
    )


# ---------------------------------------------------------------------------
# 5 - API / no-API matrix per target system
# ---------------------------------------------------------------------------

def api_matrix(bots: list[Taskbot]) -> list[dict]:
    rows: dict[str, dict] = {}
    for b in bots:
        row = rows.setdefault(b.target_system, {
            "target_system": b.target_system,
            "has_api": b.has_api,
            "bots": 0,
            "monthly_volume": 0,
        })
        row["bots"] += 1
        row["monthly_volume"] += b.monthly_volume
        # if any bot on the system declares an API, the system has one
        row["has_api"] = row["has_api"] or b.has_api
    for row in rows.values():
        row["needs_api_exposure"] = not row["has_api"]
    return sorted(rows.values(), key=lambda r: (-r["monthly_volume"],))


# ---------------------------------------------------------------------------
# Orchestration -> Wave 0 catalog
# ---------------------------------------------------------------------------

def run_discovery(inventory_path: str, threshold: float = JACCARD_THRESHOLD) -> dict:
    bots = load_inventory(inventory_path)
    clusters = cluster_taskbots(bots, threshold)
    capabilities = [decide_capability(c) for c in clusters]

    total_bots = len(bots)
    total_capabilities = len(capabilities)
    reduction = round(1 - total_capabilities / total_bots, 3) if total_bots else 0.0

    counts = {MIGRATE: 0, CONSOLIDATE: 0, RETIRE: 0}
    for cap in capabilities:
        for decision in cap.bot_decisions.values():
            counts[decision] += 1

    ranking = sorted(capabilities, key=lambda c: c.canonical_score, reverse=True)

    return {
        "summary": {
            "total_taskbots": total_bots,
            "total_capabilities": total_capabilities,
            "estimated_reduction_pct": round(reduction * 100, 1),
            "jaccard_threshold": threshold,
            "decisions": counts,
            "blocked_by_api": [c.capability_id for c in capabilities if c.blocked_by_api],
        },
        "api_matrix": api_matrix(bots),
        "capabilities": [asdict(c) for c in ranking],
    }


# Spanish labels for the human-readable deliverable (code stays English).
DECISION_LABEL_ES = {MIGRATE: "MIGRAR", CONSOLIDATE: "CONSOLIDAR", RETIRE: "RETIRAR"}


def render_markdown(catalog: dict) -> str:
    s = catalog["summary"]
    d = s["decisions"]
    out = ["# Catalogo Ola 0 (salida del discovery)", ""]
    out.append(f"- **Taskbots inventariados:** {s['total_taskbots']}")
    out.append(f"- **Capacidades reales (clusters):** {s['total_capabilities']}")
    out.append(f"- **Reduccion estimada:** {s['estimated_reduction_pct']}%  "
               f"(umbral Jaccard = {s['jaccard_threshold']})")
    out.append(f"- **Decisiones:** MIGRAR {d[MIGRATE]} / "
               f"CONSOLIDAR {d[CONSOLIDATE]} / RETIRAR {d[RETIRE]}")
    out.append(f"- **Bloqueados por API faltante:** {len(s['blocked_by_api'])} capacidades")
    out.append("")
    out.append("## Matriz API / no-API por sistema destino")
    out.append("")
    out.append("| Sistema destino | Tiene API | Bots | Volumen/mes | Requiere exposicion |")
    out.append("|---|---|---|---|---|")
    for row in catalog["api_matrix"]:
        out.append(f"| {row['target_system']} | {'Si' if row['has_api'] else 'No'} "
                   f"| {row['bots']} | {row['monthly_volume']:,} "
                   f"| {'SI' if row['needs_api_exposure'] else '-'} |")
    out.append("")
    out.append("## Capacidades priorizadas (top por score)")
    out.append("")
    out.append("| Capacidad | Destino | Bots | Decision | Score | Bloqueo API |")
    out.append("|---|---|---|---|---|---|")
    for c in catalog["capabilities"]:
        out.append(f"| {c['capability_id']} | {c['target_system']} | {len(c['taskbots'])} "
                   f"| {DECISION_LABEL_ES[c['cluster_decision']]} | {c['canonical_score']} "
                   f"| {'SI' if c['blocked_by_api'] else '-'} |")
    return "\n".join(out) + "\n"


def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    inventory = os.path.join(here, "sample_inventory.csv")
    out_dir = os.path.join(here, "out")
    os.makedirs(out_dir, exist_ok=True)

    catalog = run_discovery(inventory)

    with open(os.path.join(out_dir, "wave0_catalog.json"), "w", encoding="utf-8") as fh:
        json.dump(catalog, fh, ensure_ascii=False, indent=2)
    markdown = render_markdown(catalog)
    with open(os.path.join(out_dir, "wave0_catalog.md"), "w", encoding="utf-8") as fh:
        fh.write(markdown)

    print(markdown)


if __name__ == "__main__":
    main()
