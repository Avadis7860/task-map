"""test_classify — machine à états, prédicats de trigger/DoD, helpers de requête (moteur porté).

Rejoue les contrats de la moitié « état » de `vault_tasks.py` sur le corpus de fixtures.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from taskmap.classify import (
    burndown,
    classify,
    evaluate_dod_criteria,
    evaluate_trigger,
    tree_stats,
)
from taskmap.graph import load_tasks

FIXT = Path(__file__).resolve().parent / "fixtures" / "vault"
TODAY = "2026-07-14"


@pytest.fixture
def classified():
    index, _ = load_tasks(FIXT)
    return classify(index, FIXT, TODAY)


@pytest.mark.parametrize("tid,state", [
    ("done-task", "DONE"),
    ("cancelled-task", "CANCELLED"),
    ("active-task", "ACTIVE"),
    ("ready-task", "READY"),
    ("blocked-deps", "BLOCKED_DEPS"),
    ("dangling-dep", "ERROR"),
    ("deferred-glob", "DEFERRED"),
    ("deferred-manual", "DEFERRED"),
    ("cycle-a", "CYCLE"),
    ("cycle-b", "CYCLE"),
    ("ROADMAP-demo", "EPIC"),
    ("hors-vocab", "READY"),          # hors-vocab n'affecte pas l'état
    ("blocked-by-alias", "READY"),    # blocked_by unionné, dep done → READY
    ("demo-p1", "READY"),             # dep de phase demo-p0 (done) → READY
])
def test_states(classified, tid, state):
    assert classified[tid]["state"] == state


def test_epic_not_closable_with_pending_child(classified):
    epic = classified["ROADMAP-demo"]
    assert epic["epic_closable"] is False               # demo-p1 encore backlog
    assert any("demo-p1" in b for b in epic["blockers"])


def test_dangling_blocker_message(classified):
    assert classified["dangling-dep"]["blockers"] == ["does-not-exist (AUCUN FICHIER TASK)"]


def test_evaluate_trigger_predicates():
    index, _ = load_tasks(FIXT)
    assert evaluate_trigger(None, FIXT, index, TODAY)[0] is True
    assert evaluate_trigger({"when": "manual"}, FIXT, index, TODAY)[0] is False
    assert evaluate_trigger({"when": "task_done", "id": "done-task"}, FIXT, index, TODAY)[0] is True
    assert evaluate_trigger({"when": "task_done", "id": "ready-task"}, FIXT, index, TODAY)[0] is False
    assert evaluate_trigger({"when": "path_exists", "path": "docs/exists.md"}, FIXT, index, TODAY)[0] is True
    assert evaluate_trigger({"when": "path_exists", "path": "docs/nope.md"}, FIXT, index, TODAY)[0] is False
    assert evaluate_trigger({"when": "date_after", "date": "2026-01-01"}, FIXT, index, TODAY)[0] is True
    assert evaluate_trigger({"when": "date_after", "date": "2099-01-01"}, FIXT, index, TODAY)[0] is False
    # prose / grammaire invalide → conservateur (non franchi)
    assert evaluate_trigger("attendre un signal", FIXT, index, TODAY)[0] is False
    # composition any_of / all_of
    ok = evaluate_trigger({"any_of": [{"when": "manual"}, {"when": "task_done", "id": "done-task"}]},
                          FIXT, index, TODAY)[0]
    assert ok is True
    ko = evaluate_trigger({"all_of": [{"when": "manual"}, {"when": "task_done", "id": "done-task"}]},
                          FIXT, index, TODAY)[0]
    assert ko is False


def test_glob_scope_guard_rejects_traversal():
    index, _ = load_tasks(FIXT)
    bad = evaluate_trigger({"when": "glob_count", "glob": "../**", "op": ">=", "value": 1}, FIXT, index)
    assert bad[0] is False and "non scopé" in bad[1]


def test_evaluate_dod_criteria():
    index, _ = load_tasks(FIXT)
    crit = index["dod-task"]["dod_criteria"]
    ok, results = evaluate_dod_criteria(crit, FIXT, index, today=TODAY)
    assert ok is True and len(results) == 2
    # None/[] → régie prose (True, [])
    assert evaluate_dod_criteria(None, FIXT, index) == (True, [])
    # un prédicat non supporté en clôture (manual) → jamais un faux-vert
    ko, _ = evaluate_dod_criteria([{"when": "manual"}], FIXT, index)
    assert ko is False


def test_tree_stats_and_burndown(classified):
    stats = tree_stats(classified)
    assert stats["done"] >= 1 and stats["ready"] >= 1 and stats["blocked"] >= 1
    bd = burndown(classified)
    assert bd["total"] >= bd["done"] >= 1 and 0.0 <= bd["ratio"] <= 1.0
