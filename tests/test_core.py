"""test_core — contrat du cœur de graphe GÉNÉRIQUE (`taskmap.core.graph`), éprouvé façon consommateur tiers.

Zéro markdown, zéro slot STAMP : des dicts plats (la forme que le cockpit projettera depuis ses rows SQLite).
Verrouille : parité de `detect_cycles` après déplacement, le **lift transitif** de `eff_prio` (un P3 qui
débloque un P0 devient NEXT), et l'ordre total de `rank_ready`/`resolve_next` (tiebreak `id`, robustesse au
cycle, fallback priorité inconnue, filtrage `scope_pred`).
"""
from __future__ import annotations

from taskmap.core.graph import (
    detect_cycles,
    eff_prio,
    rank_ready,
    resolve_next,
)

PRIO = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


def _ready(**over) -> dict:
    """Record générique READY minimal (façon row projeté cockpit : id, priority, depends_on, created)."""
    rec = {"id": "x", "state": "READY", "priority": "P2", "depends_on": [], "created": ""}
    rec.update(over)
    return rec


# -- detect_cycles : parité post-déplacement -------------------------------------------------------

def test_detect_cycles_flat_index():
    index = {
        "a": {"depends_on": ["b"]},
        "b": {"depends_on": ["a"]},   # a↔b cycle
        "c": {"depends_on": ["a"]},   # c pointe dans le cycle mais n'en est pas membre
    }
    assert detect_cycles(index) == {"a", "b"}


def test_detect_cycles_ignores_dangling():
    index = {"a": {"depends_on": ["ghost"]}}   # arête vers un id absent → ignorée, pas de crash
    assert detect_cycles(index) == set()


def test_detect_cycles_empty():
    assert detect_cycles({}) == set()


# -- eff_prio : lift transitif (le cœur de la graduation) ------------------------------------------

def test_eff_prio_transitive_lift():
    """Un P3 qui débloque un P0 hérite du rang P0 (il est sur le chemin critique)."""
    index = {
        "p0": {"priority": "P0", "depends_on": ["p3"]},   # p0 dépend de p3
        "p3": {"priority": "P3", "depends_on": []},       # p3 débloque p0 → doit remonter
    }
    effp = eff_prio(index, PRIO)
    assert effp["p3"] == 0        # lifté au rang de p0 (0), pas son rang propre (3)
    assert effp["p0"] == 0


def test_eff_prio_leaf_keeps_own_rank():
    """Sans dépendant, la priorité effective == la priorité propre (record dep-less inclus)."""
    index = {"solo": {"priority": "P3", "depends_on": []}, "nodeps": {"priority": "P1"}}
    effp = eff_prio(index, PRIO)
    assert effp["solo"] == 3
    assert effp["nodeps"] == 1    # `depends_on` absent → traité feuille, pas de crash


def test_eff_prio_unknown_priority_is_last():
    index = {"weird": {"priority": "P9", "depends_on": []}}
    assert eff_prio(index, PRIO)["weird"] == len(PRIO)   # hors-vocab → dernier


def test_eff_prio_cycle_safe():
    """Garde de pile : un cycle ne provoque pas de récursion infinie."""
    index = {
        "a": {"priority": "P2", "depends_on": ["b"]},
        "b": {"priority": "P1", "depends_on": ["a"]},   # a↔b
    }
    effp = eff_prio(index, PRIO)
    assert effp["a"] == 1 and effp["b"] == 1   # chacun voit le meilleur du cycle (P1)


# -- rank_ready / resolve_next : ordre total -------------------------------------------------------

def test_resolve_next_prefers_transitive_unblocker():
    """resolve_next classe le P3 qui débloque un P0 EN TÊTE des READY (il est la NEXT dispatchable)."""
    index = {
        "p0": _ready(id="p0", priority="P0", depends_on=["p3"], state="BLOCKED_DEPS"),
        "p3": _ready(id="p3", priority="P3", depends_on=[]),
        "p2": _ready(id="p2", priority="P2", depends_on=[]),
    }
    nxt = resolve_next(index, PRIO)
    assert nxt is not None and nxt["id"] == "p3"   # p3 (eff 0) devance p2 (eff 2)


def test_rank_ready_tiebreak_by_id():
    """À priorité effective ET date égales, l'`id` tranche (ordre total, zéro ex-æquo)."""
    index = {
        "beta": _ready(id="beta", priority="P1", created="2026-01-01"),
        "alpha": _ready(id="alpha", priority="P1", created="2026-01-01"),
    }
    order = [t["id"] for t in rank_ready(index, PRIO)]
    assert order == ["alpha", "beta"]


def test_rank_ready_created_before_id():
    """La date de création prime sur l'id (une task plus ancienne passe devant)."""
    index = {
        "z-old": _ready(id="z-old", priority="P1", created="2026-01-01"),
        "a-new": _ready(id="a-new", priority="P1", created="2026-06-01"),
    }
    order = [t["id"] for t in rank_ready(index, PRIO)]
    assert order == ["z-old", "a-new"]   # date ↑ avant tiebreak id


def test_rank_ready_filters_non_ready_and_scope():
    index = {
        "in": _ready(id="in", priority="P0"),
        "out-state": _ready(id="out-state", priority="P0", state="BLOCKED_DEPS"),
        "out-scope": _ready(id="out-scope", priority="P0"),
    }
    order = [t["id"] for t in rank_ready(index, PRIO, scope_pred=lambda t: t["id"] != "out-scope")]
    assert order == ["in"]   # non-READY exclu par état, out-scope exclu par prédicat


def test_resolve_next_none_when_no_ready():
    index = {"blocked": _ready(id="blocked", state="BLOCKED_DEPS")}
    assert resolve_next(index, PRIO) is None
