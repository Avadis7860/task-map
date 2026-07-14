"""northstar — chargement + validation du manifeste north-star (projection de la SoT prose du repo cible).

Le manifeste (déclaré par `.taskmap.toml [northstar].manifest`, ex. `.claude/northstar.yaml`) encode les
**axes** de la north-star, la **carte épic→axe** (rollup) et les **gates**. Ce module le CHARGE (parseur
stdlib de `frontmatter`, zéro dépendance) et le VALIDE par **prédicats purs** (I4 du blueprint
`deterministic-tooling-gate`) : un lien mort est **signalé, jamais deviné**. Le rollup `axis_for_epic` est le
cœur consommé par le verbe `context`/`rollup` (câblage CLI = P5) ; ici on ne livre que **donnée + loader +
validateur + selftest**.

SoT-and-derive (I1) : la prose narre (`corpus/decision/meta/*north-star*`), ce YAML dérive ; l'`axis` d'une
task est **dérivé** (épic → axe primaire), jamais stocké — pas de 2ᵉ source de vérité.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from taskmap import frontmatter

# Version du schéma du MANIFESTE (distincte du SCHEMA_VERSION du contrat de sortie taskmap). Additive.
MANIFEST_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class Axis:
    """Un axe north-star + ses flags de pondération (dry : booléens, pas de prose)."""

    id: str
    order: int
    differentiator: bool = False   # l'axe différenciateur (v2 §3, axe 3)
    underweighted: bool = False    # sous-pondéré à rattraper (rebalance v2 §4)
    additive: bool = False         # axe additif (v3, axe 4)


@dataclass(frozen=True)
class Manifest:
    """Manifeste north-star résolu. `epics` : id → {axis: str|None, also_serves: tuple[str, ...]}."""

    schema_version: str
    axes: tuple[Axis, ...]
    epics: dict[str, dict[str, Any]]
    gates: dict[str, tuple[str, ...]]   # gate_id → axes jugés
    doctrine: tuple[str, ...]
    prose_sot: tuple[str, ...]

    @property
    def axis_ids(self) -> frozenset[str]:
        return frozenset(a.id for a in self.axes)


def parse_manifest(data: Any) -> Manifest:
    """Construit un `Manifest` depuis le dict brut (déjà parsé). Tolérant : champ absent → défaut sûr, une
    entrée mal formée est ignorée (la validation, elle, signale les liens morts). Ne lève jamais."""
    if not isinstance(data, dict):
        data = {}
    axes = tuple(
        Axis(
            id=str(a["id"]),
            order=int(a.get("order", i)),
            differentiator=a.get("differentiator") is True,
            underweighted=a.get("underweighted") is True,
            additive=a.get("additive") is True,
        )
        for i, a in enumerate(data.get("axes") or [])
        if isinstance(a, dict) and a.get("id")
    )
    epics: dict[str, dict[str, Any]] = {}
    for eid, spec in (data.get("epics") or {}).items():
        if not isinstance(spec, dict):
            continue
        axis = spec.get("axis")
        epics[str(eid)] = {
            "axis": str(axis) if axis else None,
            "also_serves": tuple(str(x) for x in (spec.get("also_serves") or [])),
        }
    gates: dict[str, tuple[str, ...]] = {
        str(gid): tuple(str(x) for x in (spec.get("judges") or []))
        for gid, spec in (data.get("gates") or {}).items()
        if isinstance(spec, dict)
    }
    return Manifest(
        schema_version=str(data.get("schema_version", "")),
        axes=axes,
        epics=epics,
        gates=gates,
        doctrine=tuple(str(x) for x in (data.get("doctrine") or [])),
        prose_sot=tuple(str(x) for x in (data.get("prose_sot") or [])),
    )


def load_manifest(path: str | Path) -> Manifest:
    """Charge + parse le manifeste YAML à `path` (parseur stdlib). Fichier absent → `FileNotFoundError`."""
    text = Path(path).read_text(encoding="utf-8")
    return parse_manifest(frontmatter.load(text))


def validate(m: Manifest) -> list[str]:
    """Prédicats purs → liste d'erreurs (liens morts). Liste **vide = cohérent**. Ne lève jamais.

    Vérifie : ids d'axes uniques ; tout `epic.axis` et `also_serves` ∈ axes ; tout `gate.judges` ∈ axes."""
    errors: list[str] = []
    ids = [a.id for a in m.axes]
    axis_ids = set(ids)
    for aid in sorted(axis_ids):
        if ids.count(aid) > 1:
            errors.append(f"axe dupliqué : {aid}")
    for eid, spec in m.epics.items():
        axis = spec.get("axis")
        if not axis:
            errors.append(f"épic sans axe : {eid}")
        elif axis not in axis_ids:
            errors.append(f"épic {eid} → axe inconnu : {axis}")
        for extra in spec.get("also_serves", ()):
            if extra not in axis_ids:
                errors.append(f"épic {eid} also_serves un axe inconnu : {extra}")
    for gid, judged in m.gates.items():
        for axis in judged:
            if axis not in axis_ids:
                errors.append(f"gate {gid} juge un axe inconnu : {axis}")
    return errors


def axis_for_epic(m: Manifest, epic_id: str) -> str | None:
    """Rollup pur : l'axe **primaire** (cardinalité 1) de l'épic, ou `None` s'il n'est pas dans la carte."""
    spec = m.epics.get(epic_id)
    return spec.get("axis") if spec else None


_SELFTEST_OK = (
    'schema_version: "1.0"\n'
    "axes:\n"
    "  - {id: a1, order: 1}\n"
    "  - {id: a2, order: 2, differentiator: true, underweighted: true}\n"
    "epics:\n"
    "  ROADMAP-x: {axis: a1}\n"
    "  ROADMAP-y: {axis: a2, also_serves: [a1]}\n"
    "gates:\n"
    "  g1: {judges: [a1, a2]}\n"
    "doctrine: [d1]\n"
)
_SELFTEST_BROKEN = (
    "axes:\n"
    "  - {id: a1, order: 1}\n"
    "epics:\n"
    "  ROADMAP-z: {axis: ghost}\n"
    "gates:\n"
    "  g: {judges: [phantom]}\n"
)


def selftest() -> None:
    """Selftest in-module (I4) : loader + flags + validateur + rollup, sur deux docs en mémoire."""
    m = parse_manifest(frontmatter.load(_SELFTEST_OK))
    assert m.schema_version == "1.0", m.schema_version
    assert m.axis_ids == {"a1", "a2"}, m.axis_ids
    assert [a.order for a in m.axes] == [1, 2]
    assert any(a.differentiator and a.underweighted for a in m.axes)
    assert validate(m) == [], validate(m)
    assert axis_for_epic(m, "ROADMAP-x") == "a1"
    assert axis_for_epic(m, "ROADMAP-y") == "a2"
    assert m.epics["ROADMAP-y"]["also_serves"] == ("a1",)
    assert axis_for_epic(m, "absent") is None
    broken = parse_manifest(frontmatter.load(_SELFTEST_BROKEN))
    errs = validate(broken)
    assert any("ghost" in e for e in errs) and any("phantom" in e for e in errs), errs


if __name__ == "__main__":
    selftest()
    print("northstar selftest OK")
