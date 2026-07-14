"""test_graph — chargement, DAG, dérivation de phases, cycles, enfants d'épic, réconciliation (moteur porté).

Rejoue les contrats de la moitié « structure » de `vault_tasks.py` sur le corpus de fixtures synthétique.
"""
from __future__ import annotations

from pathlib import Path

from taskmap.graph import (
    _children,
    derive_phase_deps,
    detect_cycles,
    load_tasks,
    reconcile_epics,
)

FIXT = Path(__file__).resolve().parent / "fixtures" / "vault"


def test_load_covers_all_buckets():
    index, _ = load_tasks(FIXT)
    assert {"done-task", "cancelled-task", "active-task", "ready-task", "ROADMAP-demo"} <= set(index)
    assert index["done-task"]["bucket"] == "archive"
    assert index["active-task"]["bucket"] == "active"
    assert index["ready-task"]["bucket"] == "backlog"


def test_blocked_by_alias_unioned_with_warning():
    index, warnings = load_tasks(FIXT)
    assert index["blocked-by-alias"]["depends_on"] == ["done-task"]
    assert any("blocked_by" in w and "blocked-by-alias" in w for w in warnings)


def test_hors_vocab_failsoft_warnings():
    index, warnings = load_tasks(FIXT)
    rec = index["hors-vocab"]
    assert rec["service"] == "" and rec["category"] == "" and rec["env"] == ""   # invalides → ignorés
    assert rec["priority"] == "P9"                                               # conservé mais signalé
    assert any("priority hors vocab" in w for w in warnings)
    assert any("env invalide" in w for w in warnings)
    assert any("service invalide" in w for w in warnings)
    assert any("category invalide" in w for w in warnings)


def test_phase_deps_derived_from_manifest():
    index, _ = load_tasks(FIXT)
    # étape 2 (demo-p1) dépend de l'étape 1 (demo-p0), dérivé du manifeste `phases:` de ROADMAP-demo.
    assert "demo-p0" in index["demo-p1"]["depends_on"]
    assert index["demo-p1"]["phase_deps"].get("demo-p0") == "ROADMAP-demo"


def test_derive_phase_deps_is_idempotent():
    index, _ = load_tasks(FIXT)
    before = list(index["demo-p1"]["depends_on"])
    derive_phase_deps(index)                     # ré-appliquer n'ajoute pas de doublon
    assert index["demo-p1"]["depends_on"] == before


def test_detect_cycles():
    index, _ = load_tasks(FIXT)
    assert detect_cycles(index) == {"cycle-a", "cycle-b"}


def test_children_of_epic():
    index, _ = load_tasks(FIXT)
    kids = {k["id"] for k in _children(index, "ROADMAP-demo")}
    assert kids == {"demo-p0", "demo-p1"}


def test_reconcile_epics_flags_nothing_when_consistent():
    index, _ = load_tasks(FIXT)
    warns = reconcile_epics(index)
    # demo-p0 coché [x] est done ; demo-p1 décoché [ ] est backlog → aucune dérive.
    assert not any("demo-p0" in w or "demo-p1" in w for w in warns)
