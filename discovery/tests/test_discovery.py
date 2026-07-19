"""Tests for the Wave 0 discovery engine: signatures, clustering, scoring, decisions."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import discovery as d  # noqa: E402

INVENTORY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "sample_inventory.csv")


# ---- Jaccard -------------------------------------------------------------

def test_jaccard_returns_one_for_identical_sets():
    assert d.jaccard({"a", "b"}, {"a", "b"}) == 1.0


def test_jaccard_returns_zero_for_disjoint_sets():
    assert d.jaccard({"a"}, {"b"}) == 0.0


def test_jaccard_returns_partial_overlap():
    assert d.jaccard({"a", "b"}, {"b", "c"}) == 1 / 3


def test_jaccard_treats_two_empty_sets_as_equal():
    assert d.jaccard(set(), set()) == 1.0


# ---- Inventory loading ---------------------------------------------------

def test_loads_full_inventory_with_valid_ranges():
    bots = d.load_inventory(INVENTORY)
    assert len(bots) == 44
    assert all(1 <= b.criticality <= 5 for b in bots)


def test_signature_includes_steps_and_prefixed_systems():
    bots = d.load_inventory(INVENTORY)
    rec = next(b for b in bots if b.bot_id == "REC-001")
    assert "login" in rec.signature
    assert "sys:SAP" in rec.signature


# ---- Clustering ----------------------------------------------------------

def test_groups_exact_duplicates_into_the_same_cluster():
    bots = d.load_inventory(INVENTORY)
    clusters = d.cluster_taskbots(bots)
    by_bot = {b.bot_id: i for i, c in enumerate(clusters) for b in c}
    # REC-001 and its variant REC-005 (COP v2, same signature) belong together
    assert by_bot["REC-001"] == by_bot["REC-005"]


def test_never_mixes_bots_hitting_different_target_systems():
    bots = d.load_inventory(INVENTORY)
    clusters = d.cluster_taskbots(bots)
    by_bot = {b.bot_id: i for i, c in enumerate(clusters) for b in c}
    # Onboarding (SIFIN) and statement extraction (PortalWeb) are never together
    assert by_bot["ON-001"] != by_bot["EXT-001"]


def test_higher_threshold_fragments_more_than_a_lower_one():
    bots = d.load_inventory(INVENTORY)
    loose = d.cluster_taskbots(bots, threshold=0.5)
    strict = d.cluster_taskbots(bots, threshold=0.95)
    assert len(strict) >= len(loose)


def test_clustering_reduces_the_bot_count():
    bots = d.load_inventory(INVENTORY)
    clusters = d.cluster_taskbots(bots)
    # the inventory contains duplicates: fewer clusters than bots
    assert len(clusters) < len(bots)


# ---- Scoring -------------------------------------------------------------

def test_priority_score_stays_within_one_to_five():
    bots = d.load_inventory(INVENTORY)
    for b in bots:
        assert 1.0 <= d.priority_score(b, 1) <= 5.0


def test_score_weights_add_up_to_one():
    assert round(sum(d.WEIGHTS.values()), 6) == 1.0


def test_consolidation_factor_grows_with_cluster_size():
    assert d.consolidation_factor(1) < d.consolidation_factor(6)


def test_lower_complexity_yields_a_higher_score():
    easy = d.Taskbot("X", "x", "N", "SAP", True, 3000, 4, 1, 1, 1, ["login"], ["SAP"])
    hard = d.Taskbot("Y", "y", "N", "SAP", True, 3000, 4, 5, 1, 1, ["login"], ["SAP"])
    assert d.priority_score(easy, 1) > d.priority_score(hard, 1)


# ---- Decision ------------------------------------------------------------

def test_retires_a_low_value_cluster():
    bots = d.load_inventory(INVENTORY)
    obsolete = [b for b in bots if b.bot_id == "OBS-001"]
    capability = d.decide_capability(obsolete)
    assert capability.cluster_decision == d.RETIRE


def test_flags_api_block_when_migrating_a_system_without_api():
    bots = d.load_inventory(INVENTORY)
    # Onboarding on SIFIN has no API -> the canonical MIGRATE must be blocked
    onboarding = [b for b in bots if b.bot_id.startswith("ON-")]
    capability = d.decide_capability(onboarding)
    assert capability.cluster_decision == d.MIGRATE
    assert capability.blocked_by_api is True


def test_marks_exactly_one_bot_to_migrate_per_cluster():
    bots = d.load_inventory(INVENTORY)
    onboarding = [b for b in bots if b.bot_id.startswith("ON-")]
    capability = d.decide_capability(onboarding)
    migrating = [k for k, v in capability.bot_decisions.items() if v == d.MIGRATE]
    assert len(migrating) == 1


# ---- API matrix ----------------------------------------------------------

def test_api_matrix_detects_systems_without_api():
    bots = d.load_inventory(INVENTORY)
    matrix = d.api_matrix(bots)
    without_api = {r["target_system"] for r in matrix if r["needs_api_exposure"]}
    assert "SIFIN" in without_api        # core without exposed API
    assert "PortalSFC" in without_api    # regulatory portal


def test_api_matrix_marks_switch_as_api_ready():
    bots = d.load_inventory(INVENTORY)
    matrix = d.api_matrix(bots)
    switch = next(r for r in matrix if r["target_system"] == "SwitchTarjetas")
    assert switch["has_api"] is True
    assert switch["needs_api_exposure"] is False


# ---- Wave 0 catalog ------------------------------------------------------

def test_catalog_reports_a_consistent_summary():
    catalog = d.run_discovery(INVENTORY)
    summary = catalog["summary"]
    assert summary["total_taskbots"] == 44
    assert summary["total_capabilities"] < 44
    assert 0 < summary["estimated_reduction_pct"] < 100
    assert set(summary["decisions"]) == {d.MIGRATE, d.CONSOLIDATE, d.RETIRE}


def test_catalog_keeps_every_bot():
    catalog = d.run_discovery(INVENTORY)
    ids = {b for c in catalog["capabilities"] for b in c["taskbots"]}
    assert len(ids) == 44


def test_markdown_render_is_not_empty():
    catalog = d.run_discovery(INVENTORY)
    markdown = d.render_markdown(catalog)
    assert "Catalogo Ola 0" in markdown
    assert "Matriz API" in markdown
