"""test_northstar — loader + validateurs purs + rollup du manifeste north-star (P3).

Le manifeste encode axes + carte épic→axe + gates (projection de la SoT prose du repo cible). Ces tests
figent le contrat du loader stdlib et des prédicats de validation (liens morts), plus le rollup cardinalité-1.
"""
from __future__ import annotations

from pathlib import Path

from taskmap import frontmatter
from taskmap.northstar import axis_for_epic, load_manifest, parse_manifest, selftest, validate

FIXT = Path(__file__).resolve().parent / "fixtures" / "northstar"


def test_selftest_passes():
    selftest()  # ne lève pas


def test_load_valid_manifest():
    m = load_manifest(FIXT / "valid.yaml")
    assert m.schema_version == "1.0"
    assert m.axis_ids == {"alpha", "beta", "gamma"}
    assert [a.order for a in m.axes] == [1, 2, 3]
    beta = next(a for a in m.axes if a.id == "beta")
    assert beta.differentiator and beta.underweighted
    assert next(a for a in m.axes if a.id == "gamma").additive
    assert m.prose_sot == ("ns-a", "ns-b")
    assert m.doctrine == ("d1", "d2")
    assert m.gates["gate-x"] == ("alpha", "beta")


def test_valid_manifest_has_no_dead_links():
    assert validate(load_manifest(FIXT / "valid.yaml")) == []


def test_rollup_axis_for_epic():
    m = load_manifest(FIXT / "valid.yaml")
    assert axis_for_epic(m, "ROADMAP-one") == "alpha"
    assert axis_for_epic(m, "ROADMAP-two") == "beta"          # axe PRIMAIRE, jamais also_serves
    assert m.epics["ROADMAP-two"]["also_serves"] == ("gamma",)
    assert axis_for_epic(m, "inconnu") is None                # hors carte → None honnête


def test_broken_manifest_flags_dead_links():
    m = load_manifest(FIXT / "broken.yaml")
    errs = validate(m)
    assert any("nonexistent" in e for e in errs)              # epic.axis mort
    assert any("phantom" in e for e in errs)                  # also_serves mort
    assert any("ghost" in e for e in errs)                    # gate.judges mort
    assert axis_for_epic(m, "ROADMAP-ok") == "alpha"          # l'épic bien formé résout quand même


def test_duplicate_axis_is_flagged():
    doc = "axes:\n  - {id: dup, order: 1}\n  - {id: dup, order: 2}\n"
    errs = validate(parse_manifest(frontmatter.load(doc)))
    assert any("dupliqué" in e for e in errs)


def test_epic_without_axis_is_flagged():
    doc = "axes:\n  - {id: a, order: 1}\nepics:\n  ROADMAP-x: {also_serves: [a]}\n"
    errs = validate(parse_manifest(frontmatter.load(doc)))
    assert any("sans axe" in e for e in errs)


def test_parse_tolerates_missing_sections():
    m = parse_manifest(frontmatter.load('schema_version: "1.0"\n'))
    assert m.axes == () and m.epics == {} and m.gates == {}
    assert validate(m) == []       # rien à valider → cohérent
