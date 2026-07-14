"""test_cli — les verbes P5 de bout en bout via `main(argv)` (enveloppe JSON, rc, écriture réelle).

Prouve : `context`/`rollup`/`doctor` émettent l'enveloppe `{ok, schema_version}` (rc 0) ; `link`/`unlink`
consomment `authoring` (dry-run = diff sans écriture, apply = fichier muté, idempotent) ; `axis=` refusé ;
posture invalide et task absente → `ok:false` sans crash (rc 0).
"""
from __future__ import annotations

import json
from pathlib import Path

from taskmap.cli import main

DOC = """---
id: demo
status: active
priority: P1
created: 2026-07-14
updated: 2026-07-14
depends_on: [amont]
env: vault
next: "action : voir `truc`"
---

# Objectif final

Corps.
"""

MANIFEST = """schema_version: "1.0"
axes:
  - {id: surface-reseau-social, order: 3}
epics:
  ROADMAP-task-map: {axis: surface-reseau-social}
"""


def _vault(root: Path) -> None:
    (root / ".claude").mkdir(parents=True, exist_ok=True)
    (root / ".claude" / "northstar.yaml").write_text(MANIFEST, encoding="utf-8")
    (root / ".taskmap.toml").write_text(
        '[tasks]\nsubdir = [".claude", "tasks"]\n[northstar]\nmanifest = ".claude/northstar.yaml"\n',
        encoding="utf-8")
    active = root / ".claude" / "tasks" / "active"
    active.mkdir(parents=True, exist_ok=True)
    (active / "demo.md").write_text(DOC, encoding="utf-8")


def _run(capsys, argv: list[str]) -> tuple[int, dict]:
    rc = main(argv)
    out = capsys.readouterr().out
    return rc, json.loads(out)


def test_context_envelope(tmp_path, capsys):
    _vault(tmp_path)
    rc, d = _run(capsys, ["context", "demo", "--root", str(tmp_path)])
    assert rc == 0 and d["ok"] is True and d["schema_version"]
    assert d["slug"] == "demo" and d["axis"] is None      # pas encore lié


def test_link_dry_run_does_not_write(tmp_path, capsys):
    _vault(tmp_path)
    rc, d = _run(capsys, ["link", "demo", "epic=ROADMAP-task-map", "--root", str(tmp_path), "--dry-run"])
    assert rc == 0 and d["dry_run"] is True and d["changed"] is True and d["diff"]
    assert "epic:" not in (tmp_path / ".claude" / "tasks" / "active" / "demo.md").read_text()


def test_link_apply_then_context_and_idempotence(tmp_path, capsys):
    _vault(tmp_path)
    _, d = _run(capsys, ["link", "demo", "epic=ROADMAP-task-map",
                         "blueprint=deterministic-tooling-gate:applies", "--root", str(tmp_path)])
    assert d["changed"] is True and d["applied"] is True
    _, ctx = _run(capsys, ["context", "demo", "--root", str(tmp_path)])
    assert ctx["axis"] == "surface-reseau-social"
    assert ctx["blueprint"]["id"] == "deterministic-tooling-gate"
    assert ctx["blueprint"]["resolved"] is False
    # ré-appliquer le même link = no-op.
    _, again = _run(capsys, ["link", "demo", "epic=ROADMAP-task-map", "--root", str(tmp_path)])
    assert again["changed"] is False and again["applied"] is False


def test_unlink_remove_and_clear(tmp_path, capsys):
    _vault(tmp_path)
    _run(capsys, ["link", "demo", "epic=ROADMAP-task-map", "serves=a,b", "--root", str(tmp_path)])
    # retrait ciblé d'un item de liste.
    _run(capsys, ["unlink", "demo", "serves=a", "--root", str(tmp_path)])
    _, ctx = _run(capsys, ["context", "demo", "--root", str(tmp_path)])
    assert ctx["serves"] == ["b"]
    # ancre nue → vide le scalaire.
    _run(capsys, ["unlink", "demo", "epic", "--root", str(tmp_path)])
    _, ctx2 = _run(capsys, ["context", "demo", "--root", str(tmp_path)])
    assert ctx2["epic"] is None and ctx2["axis"] is None


def test_axis_anchor_refused(tmp_path, capsys):
    _vault(tmp_path)
    rc, d = _run(capsys, ["link", "demo", "axis=foo", "--root", str(tmp_path)])
    assert rc == 0 and d["ok"] is False and "axis" in d["reason"]


def test_invalid_posture_refused(tmp_path, capsys):
    _vault(tmp_path)
    rc, d = _run(capsys, ["link", "demo", "blueprint=g:bogus", "--root", str(tmp_path)])
    assert rc == 0 and d["ok"] is False


def test_blueprint_missing_posture_refused(tmp_path, capsys):
    _vault(tmp_path)
    rc, d = _run(capsys, ["link", "demo", "blueprint=g", "--root", str(tmp_path)])
    assert rc == 0 and d["ok"] is False and "posture" in d["reason"]


def test_task_not_found(tmp_path, capsys):
    _vault(tmp_path)
    rc, d = _run(capsys, ["link", "absent", "epic=x", "--root", str(tmp_path)])
    assert rc == 0 and d["ok"] is False and "introuvable" in d["reason"]


def test_doctor_and_rollup(tmp_path, capsys):
    _vault(tmp_path)
    _run(capsys, ["link", "demo", "epic=ROADMAP-task-map", "--root", str(tmp_path)])
    rc, d = _run(capsys, ["doctor", "--root", str(tmp_path)])
    assert rc == 0 and d["ok"] is True and "warnings" in d
    rc2, r = _run(capsys, ["rollup", "axis", "surface-reseau-social", "--root", str(tmp_path)])
    assert rc2 == 0 and r["count"] == 1 and r["members"][0]["slug"] == "demo"
