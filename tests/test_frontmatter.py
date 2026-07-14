"""test_frontmatter — contrat du parseur stdlib (parité PyYAML sur le sous-ensemble utilisé).

Le parseur remplace PyYAML pour tenir `dependencies=[]`. Ces tests figent les formes DÉLICATES (typage
int/str/date/null/bool, flow-seq, maps imbriquées, seq-de-maps, commentaires, blocs `|`/`>`, composition
any_of) — la preuve de parité GLOBALE sur le corpus vit dans `tools/parity_check.py`.
"""
from __future__ import annotations

import datetime

from taskmap.frontmatter import load, split_frontmatter


def _fm(text: str) -> dict:
    fm, _ = split_frontmatter("---\n" + text + "\n---\ncorps")
    return fm


def test_split_boundary():
    fm, body = split_frontmatter("---\nid: x\n---\n# Titre\ncorps")
    assert fm == {"id": "x"}
    assert body.lstrip().startswith("# Titre")
    assert split_frontmatter("pas de frontmatter") == ({}, "pas de frontmatter")


def test_scalar_typing():
    fm = _fm('n: 5\nneg: -3\ns: "5"\nop: ">="\nnul:\ntil: ~\nb1: true\nb2: false\nb3: yes\nb4: no')
    assert fm["n"] == 5 and isinstance(fm["n"], int)
    assert fm["neg"] == -3
    assert fm["s"] == "5" and isinstance(fm["s"], str)   # quoté → jamais coercé
    assert fm["op"] == ">="
    assert fm["nul"] is None and fm["til"] is None
    assert fm["b1"] is True and fm["b2"] is False
    assert fm["b3"] is True and fm["b4"] is False        # YAML 1.1 yes/no


def test_date_stays_date_object():
    """Date NON quotée → `datetime.date` (comme PyYAML) ; quotée → str."""
    fm = _fm('created: 2026-07-14\nquoted: "2026-07-14"')
    assert fm["created"] == datetime.date(2026, 7, 14)
    assert fm["quoted"] == "2026-07-14" and isinstance(fm["quoted"], str)


def test_flow_sequences():
    fm = _fm("empty: []\nids: [a, b-c, d]\ntags: [epic, stamp]")
    assert fm["empty"] == []
    assert fm["ids"] == ["a", "b-c", "d"]
    assert fm["tags"] == ["epic", "stamp"]


def test_nested_map_and_int_in_map():
    fm = _fm('trigger:\n  when: glob_count\n  glob: "d/**/*.md"\n  op: ">="\n  value: 5')
    assert fm["trigger"] == {"when": "glob_count", "glob": "d/**/*.md", "op": ">=", "value": 5}
    assert isinstance(fm["trigger"]["value"], int)


def test_sequence_of_maps():
    fm = _fm("dod_criteria:\n  - when: path_exists\n    path: docs/x.md\n  - when: task_done\n    id: t")
    assert fm["dod_criteria"] == [
        {"when": "path_exists", "path": "docs/x.md"},
        {"when": "task_done", "id": "t"},
    ]


def test_any_of_nested_composition():
    fm = _fm("trigger:\n  any_of:\n    - when: task_done\n      id: a\n    - when: manual")
    assert fm["trigger"] == {"any_of": [{"when": "task_done", "id": "a"}, {"when": "manual"}]}


def test_phases_scalar_and_list_mix():
    fm = _fm("phases:\n  - solo\n  - [a, b]\n  - c")
    assert fm["phases"] == ["solo", ["a", "b"], "c"]


def test_comment_handling():
    fm = _fm('a: 1   # commentaire\nb: "x#y"\nglob: "d/**/*.md"  # trailing')
    assert fm["a"] == 1
    assert fm["b"] == "x#y"          # `#` collé dans une chaîne quotée : littéral
    assert fm["glob"] == "d/**/*.md"


def test_literal_block_scalar():
    fm = _fm("note: |\n  ligne 1\n  ligne 2")
    assert fm["note"] == "ligne 1\nligne 2\n"          # littéral : sauts préservés + clip (saut final)


def test_folded_block_scalar_strip():
    fm = _fm("note: >-\n  para sur\n  deux lignes")
    assert fm["note"] == "para sur deux lignes"        # folded + strip → une ligne, sans saut final


def test_folded_block_scalar_clip_default():
    fm = _fm("note: >\n  une ligne")
    assert fm["note"] == "une ligne\n"                 # clip (défaut) → un seul saut final


def test_load_fenceless_nested_document():
    """`load` parse un doc YAML complet SANS fences (le manifeste) : maps-de-maps + seqs imbriqués."""
    doc = (
        'schema_version: "1.0"\n'
        "axes:\n"
        "  - {id: a1, order: 1}\n"
        "  - {id: a2, order: 2, differentiator: true}\n"
        "epics:\n"
        "  ROADMAP-x: {axis: a1, also_serves: [a2]}\n"
    )
    data = load(doc)
    assert data["schema_version"] == "1.0"
    assert data["axes"] == [{"id": "a1", "order": 1}, {"id": "a2", "order": 2, "differentiator": True}]
    assert data["epics"]["ROADMAP-x"] == {"axis": "a1", "also_serves": ["a2"]}
    assert load("") == {}                              # doc vide → {}
