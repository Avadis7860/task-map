"""test_context — les verbes de LECTURE de STAMP (P5) : context / rollup / doctor + cœur pur.

Fige : extraction des slots depuis le frontmatter (le graph engine les droppe), axe DÉRIVÉ via le manifeste
(None honnête hors carte), blueprint `resolved:false` par défaut (résolution déléguée) + seam d'injection,
rollup par axe, doctor (problèmes durs vs warnings advisory). Contrat MCP : décision vault
`2026-07-14--taskmap-mcp-degradation-contract.md`.
"""
from __future__ import annotations

from pathlib import Path

from taskmap import context
from taskmap.config import Config

DOC = """---
id: demo
status: active
priority: P1
created: 2026-07-14
updated: 2026-07-14
# commentaire
depends_on: [amont]
epic: ROADMAP-task-map
serves: [t-a, t-b]
unblocks: [t-c]
blueprint: {id: some-gate, posture: applies}
template: [some-gate/step.md]
env: vault
---

# Objectif final

Corps.
"""

MANIFEST = """schema_version: "1.0"
axes:
  - {id: surface-reseau-social, order: 3, differentiator: true}
  - {id: moteur-devops-lightweight, order: 1}
epics:
  ROADMAP-task-map: {axis: surface-reseau-social}
"""


def _make_vault(root: Path, tasks: dict[str, str], *, manifest: bool = True) -> None:
    """Écrit un mini-vault jetable : .taskmap.toml (+ manifeste) + des tasks {slug: frontmatter-text}."""
    toml = '[tasks]\nsubdir = [".claude", "tasks"]\n'
    if manifest:
        toml += '[northstar]\nmanifest = ".claude/northstar.yaml"\n'
        (root / ".claude").mkdir(parents=True, exist_ok=True)
        (root / ".claude" / "northstar.yaml").write_text(MANIFEST, encoding="utf-8")
    (root / ".taskmap.toml").write_text(toml, encoding="utf-8")
    active = root / ".claude" / "tasks" / "active"
    active.mkdir(parents=True, exist_ok=True)
    for slug, text in tasks.items():
        (active / f"{slug}.md").write_text(text, encoding="utf-8")


# --- cœur pur --------------------------------------------------------------------------------------------

def test_selftest_passes():
    context.selftest()


def test_extract_stamp_full_and_empty():
    slots = context.extract_stamp(DOC)
    assert slots["epic"] == "ROADMAP-task-map"
    assert slots["serves"] == ["t-a", "t-b"]
    assert slots["unblocks"] == ["t-c"]
    assert slots["blueprint"] == {"id": "some-gate", "posture": "applies"}
    assert slots["template"] == ["some-gate/step.md"]
    empty = context.extract_stamp("---\nid: e\nstatus: active\n---\ncorps\n")
    assert empty["epic"] is None
    assert empty["serves"] == [] and empty["unblocks"] == [] and empty["template"] == []
    assert empty["blueprint"] is None


def test_blueprint_bare_scalar_tolerated():
    slots = context.extract_stamp("---\nid: e\nstatus: active\nblueprint: bare-id\n---\n")
    assert slots["blueprint"] == {"id": "bare-id", "posture": None}


def test_blueprint_verdict_default_is_delegated():
    v = context._blueprint_verdict({"id": "g", "posture": "applies"}, None)
    assert v is not None and v["resolved"] is False and v["reason"]
    assert v["id"] == "g" and v["posture"] == "applies"


def test_blueprint_verdict_injected_resolver():
    v = context._blueprint_verdict({"id": "g", "posture": "applies"}, lambda _b: {"title": "T"})
    assert v is not None and v["resolved"] is True and v["title"] == "T" and v["reason"] == ""


def test_blueprint_verdict_dead_and_crashing_resolver():
    dead = context._blueprint_verdict({"id": "g", "posture": None}, lambda _b: None)
    assert dead is not None and dead["resolved"] is False

    def _boom(_b):
        raise RuntimeError("mcp down")

    crashed = context._blueprint_verdict({"id": "g", "posture": None}, _boom)
    assert crashed is not None and crashed["resolved"] is False and "échouée" in crashed["reason"]


def test_blueprint_verdict_none_slot():
    assert context._blueprint_verdict(None, None) is None


# --- coquilles (mini-vault jetable) -----------------------------------------------------------------------

def test_build_context_derives_axis(tmp_path):
    _make_vault(tmp_path, {"demo": DOC})
    ctx = context.build_context(tmp_path, "demo", Config.load(tmp_path))
    assert ctx.get("ok", True) is True
    assert ctx["axis"] == "surface-reseau-social"       # dérivé, jamais lu
    assert ctx["epic"] == "ROADMAP-task-map"
    assert ctx["blueprint"]["resolved"] is False        # délégué par défaut
    assert ctx["serves"] == ["t-a", "t-b"]


def test_build_context_axis_none_honest_off_map(tmp_path):
    ghost = DOC.replace("ROADMAP-task-map", "ROADMAP-ghost")
    _make_vault(tmp_path, {"demo": ghost})
    ctx = context.build_context(tmp_path, "demo", Config.load(tmp_path))
    assert ctx["epic"] == "ROADMAP-ghost"
    assert ctx["axis"] is None                          # hors carte → None honnête, jamais deviné


def test_build_context_no_manifest_axis_none(tmp_path):
    _make_vault(tmp_path, {"demo": DOC}, manifest=False)
    ctx = context.build_context(tmp_path, "demo", Config.load(tmp_path))
    assert ctx["axis"] is None and ctx["epic"] == "ROADMAP-task-map"


def test_build_context_task_not_found(tmp_path):
    _make_vault(tmp_path, {"demo": DOC})
    ctx = context.build_context(tmp_path, "absent", Config.load(tmp_path))
    assert ctx["ok"] is False and "introuvable" in ctx["reason"]


def test_build_context_injected_resolver(tmp_path):
    _make_vault(tmp_path, {"demo": DOC})
    ctx = context.build_context(tmp_path, "demo", Config.load(tmp_path),
                                resolve_blueprint=lambda _b: {"title": "Le gate"})
    assert ctx["blueprint"]["resolved"] is True and ctx["blueprint"]["title"] == "Le gate"


def test_rollup_axis(tmp_path):
    other = DOC.replace("id: demo", "id: autre").replace("ROADMAP-task-map", "ROADMAP-ghost")
    _make_vault(tmp_path, {"demo": DOC, "autre": other})
    r = context.rollup_axis(tmp_path, "surface-reseau-social", Config.load(tmp_path))
    assert r["count"] == 1 and r["members"][0]["slug"] == "demo"


def test_rollup_unknown_axis_and_no_manifest(tmp_path):
    _make_vault(tmp_path, {"demo": DOC})
    bad = context.rollup_axis(tmp_path, "ghost-axis", Config.load(tmp_path))
    assert bad["ok"] is False and "inconnu" in bad["reason"]
    _make_vault(tmp_path, {"demo": DOC}, manifest=False)
    none = context.rollup_axis(tmp_path, "x", Config.load(tmp_path))
    assert none["ok"] is False and "manifeste" in none["reason"]


def test_doctor_coherent_is_ok(tmp_path):
    _make_vault(tmp_path, {"demo": DOC})
    d = context.doctor(tmp_path, Config.load(tmp_path))
    assert d["ok"] is True and d["problems"] == [] and d["checked"] == 1


def test_doctor_flags_epic_off_map(tmp_path):
    ghost = DOC.replace("ROADMAP-task-map", "ROADMAP-ghost")
    _make_vault(tmp_path, {"demo": ghost})
    d = context.doctor(tmp_path, Config.load(tmp_path))
    assert d["ok"] is False
    assert any("hors carte" in p for p in d["problems"])


def test_doctor_skips_terminal_epic_off_map(tmp_path):
    """Régression : une task TERMINALE (done/cancelled) dont l'épic est hors carte n'est PAS un problème —
    son STAMP est figé à la clôture, on ne ré-ouvre pas une task close pour re-mapper un axe retiré. Le filtre
    keye sur le STATUT (source de vérité), pas le bucket : ici la task vit en `active/` mais `status: done` →
    exemptée. Une task encore vivante hors carte reste flaggée (cf. `test_doctor_flags_epic_off_map`)."""
    dead = DOC.replace("ROADMAP-task-map", "ROADMAP-ghost").replace("status: active", "status: done")
    _make_vault(tmp_path, {"demo": dead})
    d = context.doctor(tmp_path, Config.load(tmp_path))
    assert not any("hors carte" in p for p in d["problems"])


def test_doctor_dead_blueprint_only_with_resolver(tmp_path):
    _make_vault(tmp_path, {"demo": DOC})
    # sans resolver : blueprint non résolu n'est PAS un problème dur (délégation honnête).
    assert context.doctor(tmp_path, Config.load(tmp_path))["ok"] is True
    # avec un resolver qui ne trouve rien : liaison morte signalée.
    d = context.doctor(tmp_path, Config.load(tmp_path), resolve_blueprint=lambda _b: None)
    assert d["ok"] is False and any("blueprint" in p for p in d["problems"])
