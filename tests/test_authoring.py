"""test_authoring — pose/mute des slots STAMP dans le frontmatter (P4, le volet WRITE).

Fige le contrat de mutation (décision vault `2026-07-14--stamp-write-model-contract.md`) : édition
chirurgicale ligne-à-ligne (corps/commentaires/styles préservés), rang canonique, idempotence, listes,
`axis` jamais écrit, écriture atomique via `apply_edit`. Le cœur `plan_edit` est pur (testé in-memory).
"""
from __future__ import annotations

import pytest

from taskmap.authoring import (
    AuthoringError,
    EditPlan,
    StampEdit,
    apply_edit,
    plan_edit,
    selftest,
)

# Frontmatter réaliste : commentaires `#`, ligne vide dans le bloc, `next:` double-quoté long, corps markdown.
DOC = """---
id: demo-task
status: active
priority: P1
created: 2026-07-14
updated: 2026-07-14
related_decisions:
  - corpus/decision/projects/2026-07-14--x.md   # commentaire de queue
tags: [stamp, demo]
depends_on: [amont-a]
env: vault
next: "action : voir `truc` et [[machin]], garder l'apostrophe"
---

# Objectif final

Corps **préservé** octet-pour-octet.
"""


def test_selftest_passes():
    selftest()  # ne lève pas


def test_pose_slot_at_canonical_rank_and_preserves_body():
    plan = plan_edit(DOC, StampEdit(epic="ROADMAP-x", serves_add=("t-1", "t-2")))
    assert plan.changed
    t = plan.new_text
    # slots posés dans le bloc STAMP, après depends_on, avant env, dans l'ordre canonique.
    assert t.index("depends_on:") < t.index("epic:") < t.index("serves:") < t.index("\nenv:")
    assert "epic: ROADMAP-x" in t
    assert "serves: [t-1, t-2]" in t


def test_preserves_comments_blank_lines_and_quoting():
    t = plan_edit(DOC, StampEdit(epic="ROADMAP-x")).new_text
    assert "# commentaire de queue" in t                       # commentaire de queue intact
    assert 'next: "action : voir `truc` et [[machin]], garder l\'apostrophe"' in t  # next: intact
    assert "# Objectif final\n\nCorps **préservé** octet-pour-octet." in t  # corps + ligne vide intacts
    assert "tags: [stamp, demo]" in t                          # clé voisine non reformatée


def test_diff_touches_only_added_lines():
    plan = plan_edit(DOC, StampEdit(epic="ROADMAP-x"))
    added = [ln for ln in plan.diff.splitlines() if ln.startswith("+") and not ln.startswith("+++")]
    removed = [ln for ln in plan.diff.splitlines() if ln.startswith("-") and not ln.startswith("---")]
    assert added == ["+epic: ROADMAP-x"]
    assert removed == []                                        # insertion pure, aucune ligne retirée


def test_idempotent_reapply_is_noop():
    once = plan_edit(DOC, StampEdit(epic="ROADMAP-x", serves_add=("t-1",))).new_text
    again = plan_edit(once, StampEdit(epic="ROADMAP-x", serves_add=("t-1",)))
    assert again.changed is False
    assert again.diff == ""


def test_update_scalar_and_list_union():
    base = plan_edit(DOC, StampEdit(epic="ROADMAP-x", serves_add=("t-1",))).new_text
    # update scalaire : epic écrasé, pas dupliqué.
    upd = plan_edit(base, StampEdit(epic="ROADMAP-y")).new_text
    assert "epic: ROADMAP-y" in upd and "ROADMAP-x" not in upd
    assert upd.count("epic:") == 1
    # union : ajouter un existant = no-op ; un neuf s'ordonne après.
    assert plan_edit(base, StampEdit(serves_add=("t-1",))).changed is False
    assert "serves: [t-1, t-2]" in plan_edit(base, StampEdit(serves_add=("t-2",))).new_text


def test_unlink_removes_list_line_when_empty():
    base = plan_edit(DOC, StampEdit(serves_add=("t-1", "t-2"))).new_text
    out = plan_edit(base, StampEdit(serves_remove=("t-1", "t-2")))
    assert "serves:" not in out.new_text
    # retrait partiel : garde le reste.
    assert "serves: [t-2]" in plan_edit(base, StampEdit(serves_remove=("t-1",))).new_text


def test_clear_removes_scalar_line():
    base = plan_edit(DOC, StampEdit(epic="ROADMAP-x")).new_text
    assert "epic:" not in plan_edit(base, StampEdit(clear=frozenset({"epic"}))).new_text


def test_blueprint_flow_map_and_posture_validation():
    t = plan_edit(DOC, StampEdit(blueprint=("deterministic-tooling-gate", "applies"))).new_text
    assert "blueprint: {id: deterministic-tooling-gate, posture: applies}" in t
    with pytest.raises(AuthoringError):
        plan_edit(DOC, StampEdit(blueprint=("bp", "bogus")))


def test_axis_is_never_writable():
    assert not hasattr(StampEdit(), "axis")                     # pas de champ axis
    # aucun edit ne peut produire une ligne `axis:`.
    assert "axis:" not in plan_edit(DOC, StampEdit(epic="ROADMAP-x")).new_text


def test_missing_frontmatter_is_refused():
    with pytest.raises(AuthoringError):
        plan_edit("pas de frontmatter du tout", StampEdit(epic="x"))


def test_apply_edit_writes_atomically(tmp_path):
    f = tmp_path / "demo-task.md"
    f.write_text(DOC, encoding="utf-8")
    plan = plan_edit(f.read_text(encoding="utf-8"), StampEdit(epic="ROADMAP-x"))
    assert apply_edit(f, plan) is True
    on_disk = f.read_text(encoding="utf-8")
    assert "epic: ROADMAP-x" in on_disk
    assert on_disk.endswith("Corps **préservé** octet-pour-octet.\n")  # corps + newline final intacts


def test_apply_edit_noop_when_unchanged(tmp_path):
    f = tmp_path / "demo-task.md"
    f.write_text(DOC, encoding="utf-8")
    unchanged = EditPlan(new_text=DOC, changed=False, diff="")
    assert apply_edit(f, unchanged) is False
    assert f.read_text(encoding="utf-8") == DOC                 # fichier intact
