"""test_anchors — le contrat PUBLIC `taskmap.build_stamp_edit` (grammaire d'ancre consommée par le vault).

Isolé de `test_cli` (qui exerce la CLI de bout en bout) : ces tests figent la surface que le wrapper vault
`task_map.py` (P6) importe pour parser les ancres à l'identique, au lieu de dupliquer la grammaire.
"""
from __future__ import annotations

import pytest

from taskmap import build_stamp_edit  # re-export public depuis taskmap.anchors
from taskmap.authoring import AuthoringError


def test_reexported_at_package_root():
    from taskmap import anchors
    assert build_stamp_edit is anchors.build_stamp_edit


def test_link_parses_scalar_list_and_blueprint_posture():
    edit = build_stamp_edit(["epic=ROADMAP-x", "serves=a,b", "blueprint=bp:applies"], removing=False)
    assert edit.epic == "ROADMAP-x"
    assert edit.serves_add == ("a", "b")
    assert edit.blueprint == ("bp", "applies")


def test_unlink_bare_key_clears_and_value_removes():
    edit = build_stamp_edit(["epic", "serves=a"], removing=True)
    assert "epic" in edit.clear
    assert edit.serves_remove == ("a",)


def test_axis_is_refused_structurally():
    with pytest.raises(AuthoringError):
        build_stamp_edit(["axis=surface-reseau-social"], removing=False)


def test_blueprint_requires_posture():
    with pytest.raises(AuthoringError):
        build_stamp_edit(["blueprint=bp"], removing=False)


def test_unknown_anchor_is_refused():
    with pytest.raises(AuthoringError):
        build_stamp_edit(["frobnicate=x"], removing=False)
