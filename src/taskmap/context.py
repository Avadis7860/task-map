"""context — les verbes de LECTURE de STAMP : `context` (les 3 liaisons), `rollup axis`, `doctor`.

Read-only, live. **Re-parse les slots STAMP directement du frontmatter** (`epic`/`serves`/`unblocks`/
`blueprint`/`template`) : le moteur de graphe (`graph.load_tasks`) ne les garde PAS dans son record — il ne
retient que `depends_on`. `axis` n'est JAMAIS lu ni stocké : il est **dérivé** via `northstar.axis_for_epic`
(épic → axe primaire ; `None` honnête hors carte), I1 (pas de 2ᵉ SoT).

**Résolution du blueprint ref DÉLÉGUÉE** au consommateur MCP (primaire = une session Claude, qui a déjà
`.mcp.json` + Bearer ; ou le cockpit). task-map reste offline / stdlib-pur / sans secret : par défaut le
verdict est `resolved:false` + raison honnête (jamais inventé). Un **seam d'injection** `resolve_blueprint`
permet à un consommateur programmatique de résoudre. Contrat : décision vault
`corpus/decision/projects/2026-07-14--taskmap-mcp-degradation-contract.md`.

Séparation pur/impur (I4) : `extract_stamp`/`assemble_context`/`_blueprint_verdict` sont **purs** (testés par
`selftest`) ; `build_context`/`rollup_axis`/`doctor` sont les coquilles qui lisent le corpus tasks.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from taskmap import northstar
from taskmap.classify import _warnings, classify
from taskmap.config import Config
from taskmap.frontmatter import split_frontmatter
from taskmap.graph import TERMINAL_STATUS, load_tasks, reconcile_epics

# Un resolver blueprint : id → dict de champs résolus (title/ref…), ou None/{} = injoignable/introuvable.
BlueprintResolver = Callable[[str], "dict | None"]

_DELEGATED = "résolution déléguée au consommateur MCP (non résolu localement)"
_DEAD = "blueprint injoignable ou introuvable (empty) — liaison morte à signaler"


# --- cœur pur (zéro I/O) ------------------------------------------------------------------------------------

def extract_stamp(text: str) -> dict:
    """Extrait les slots STAMP du frontmatter d'une task, en formes normalisées. PUR.

    `epic` → str|None ; `serves`/`unblocks`/`template` → list[str] ; `blueprint` → {id, posture}|None.
    `axis` n'est jamais extrait (dérivé). Une task sans slot rend des valeurs vides honnêtes.
    """
    fm, _body = split_frontmatter(text)
    return {
        "epic": _scalar(fm.get("epic")),
        "serves": _strlist(fm.get("serves")),
        "unblocks": _strlist(fm.get("unblocks")),
        "template": _strlist(fm.get("template")),
        "blueprint": _blueprint(fm.get("blueprint")),
    }


def _scalar(v: Any) -> str | None:
    return str(v) if v not in (None, "") else None


def _strlist(v: Any) -> list[str]:
    return [str(x) for x in v] if isinstance(v, list) else []


def _blueprint(v: Any) -> dict | None:
    """Normalise le slot `blueprint` : flow-map `{id, posture}`, ou scalaire nu `<id>` (posture inconnue)."""
    if isinstance(v, dict) and v.get("id"):
        posture = v.get("posture")
        return {"id": str(v["id"]), "posture": str(posture) if posture else None}
    if isinstance(v, str) and v:
        return {"id": v, "posture": None}
    return None


def _blueprint_verdict(bp: dict | None, resolve: BlueprintResolver | None) -> dict | None:
    """Verdict du slot blueprint. Défaut (aucun resolver) : `resolved:false` + raison de délégation honnête.

    Si `resolve` est fourni, on l'appelle : un dict véridique → `resolved:true` (+ champs fusionnés) ; un
    None/{} → liaison morte signalée ; une exception → échec signalé (jamais propagée). Jamais inventé.
    """
    if bp is None:
        return None
    out: dict = {"id": bp["id"], "posture": bp["posture"], "resolved": False, "reason": _DELEGATED}
    if resolve is None:
        return out
    try:
        resolved = resolve(bp["id"])
    except Exception as e:  # noqa: BLE001 — un resolver qui casse ne doit pas abattre le verbe de lecture.
        out["reason"] = f"résolution échouée : {type(e).__name__}"
        return out
    if resolved:
        out["resolved"] = True
        out["reason"] = ""
        for k, val in resolved.items():
            if k not in ("id", "posture", "resolved", "reason"):
                out[k] = val
    else:
        out["reason"] = _DEAD
    return out


def assemble_context(slug: str, slots: dict, axis: str | None, blueprint_verdict: dict | None) -> dict:
    """Assemble le payload `context` figé : slots extraits + axe dérivé + verdict blueprint. PUR."""
    return {
        "slug": slug,
        "axis": axis,
        "epic": slots["epic"],
        "serves": slots["serves"],
        "unblocks": slots["unblocks"],
        "blueprint": blueprint_verdict,
        "template": slots["template"],
    }


# --- coquilles (lecture live du corpus tasks) --------------------------------------------------------------

def _load_manifest(root: Path, config: Config) -> northstar.Manifest | None:
    """Charge le manifeste north-star si configuré + présent ; None sinon (dégradation honnête)."""
    if not config.northstar_manifest:
        return None
    p = Path(root) / config.northstar_manifest
    if not p.is_file():
        return None
    try:
        return northstar.load_manifest(p)
    except Exception:  # noqa: BLE001 — un manifeste illisible désactive le rollup, n'abat pas la lecture.
        return None


def _read(root: Path, rec: dict) -> str:
    return (root / rec["path"]).read_text(encoding="utf-8", errors="replace")


def build_context(root: Path | str, slug: str, config: Config | None = None,
                  resolve_blueprint: BlueprintResolver | None = None) -> dict:
    """Rend les 3 liaisons STAMP d'une task : axe dérivé · épic servi/`serves`/`unblocks` · blueprint (ref +
    verdict). Task absente → `{ok:false, reason}` (échec logique, rc 0 côté CLI)."""
    root = Path(root)
    config = config or Config.load(root)
    index, _warns = load_tasks(root, config)
    rec = index.get(slug)
    if rec is None:
        return {"ok": False, "slug": slug, "reason": f"task introuvable : {slug}"}
    slots = extract_stamp(_read(root, rec))
    manifest = _load_manifest(root, config)
    axis = northstar.axis_for_epic(manifest, slots["epic"]) if (manifest and slots["epic"]) else None
    verdict = _blueprint_verdict(slots["blueprint"], resolve_blueprint)
    return assemble_context(slug, slots, axis, verdict)


def rollup_axis(root: Path | str, name: str, config: Config | None = None) -> dict:
    """Agrège les tasks dont l'axe **dérivé** (épic → axe) == `name`. Pas de manifeste / axe inconnu →
    `{ok:false, reason}` (honnête)."""
    root = Path(root)
    config = config or Config.load(root)
    index, _warns = load_tasks(root, config)
    manifest = _load_manifest(root, config)
    if manifest is None:
        return {"ok": False, "dimension": "axis", "name": name,
                "reason": "pas de manifeste north-star configuré → rollup d'axe indisponible"}
    if name not in manifest.axis_ids:
        return {"ok": False, "dimension": "axis", "name": name,
                "reason": f"axe inconnu : {name} (∈ {sorted(manifest.axis_ids)})"}
    members: list[dict] = []
    for tid, rec in index.items():
        epic = extract_stamp(_read(root, rec))["epic"]
        if epic and northstar.axis_for_epic(manifest, epic) == name:
            members.append({"slug": tid, "status": rec["status"], "epic": epic})
    members.sort(key=lambda m: m["slug"])
    return {"dimension": "axis", "name": name, "count": len(members), "members": members}


def doctor(root: Path | str, config: Config | None = None,
           resolve_blueprint: BlueprintResolver | None = None) -> dict:
    """Cohérence des liaisons. `problems` (DURES → bascule `ok:false`) : graphe corrompu (dep dangling /
    cycle), manifeste north-star incohérent (`northstar.validate`), intégrité STAMP (épic hors carte ;
    blueprint mort si un resolver est fourni). `warnings` (advisory, NE bascule PAS `ok`) : l'hygiène tasks
    déjà surfacée (réconciliation ROADMAP, WIP, différés, vocab) — matériel de remontée proactive."""
    root = Path(root)
    config = config or Config.load(root)
    index, index_warns = load_tasks(root, config)
    classified = classify(index, root)
    manifest = _load_manifest(root, config)

    problems: list[str] = []
    for tid, t in classified.items():
        if t["state"] == "ERROR":
            problems += [f"dep dangling : {tid} → {b}" for b in t["blockers"]]
        elif t["state"] == "CYCLE":
            problems.append(f"cycle de dépendances : {tid}")
    if manifest is not None:
        problems += [f"north-star : {e}" for e in northstar.validate(manifest)]
    for tid, rec in index.items():
        # Intégrité STAMP = hygiène des liaisons VIVANTES. Une task TERMINALE (done/cancelled) fige son STAMP
        # à la clôture : son épic peut pointer un calendrier/axe depuis retiré de la carte sans que ce soit un
        # défaut à corriger (on ne ré-ouvre pas une task close pour re-mapper un axe mort). Filtrer par STATUT
        # (source de vérité), pas par bucket : couvre les faux positifs archivés d'un coup et n'exempte JAMAIS
        # un vrai oubli de mapping sur une task encore vivante.
        if rec["status"] in TERMINAL_STATUS:
            continue
        slots = extract_stamp(_read(root, rec))
        epic = slots["epic"]
        if epic and manifest is not None and epic not in manifest.epics:
            problems.append(f"STAMP : {tid} → epic '{epic}' hors carte north-star (axe non résolu)")
        if resolve_blueprint is not None and slots["blueprint"]:
            verdict = _blueprint_verdict(slots["blueprint"], resolve_blueprint)
            if verdict and not verdict["resolved"]:
                problems.append(
                    f"STAMP : {tid} → blueprint '{verdict['id']}' non résolu ({verdict['reason']})")

    # advisory : tout le reste, sans redoubler les incohérences dures déjà comptées.
    warnings = [w for w in (_warnings(index_warns, classified, None) + reconcile_epics(index))
                if not w.startswith(("dep dangling", "cycle de dépendances"))]

    return {"checked": len(index), "problems": problems, "warnings": warnings, "ok": not problems}


# --- selftest in-module (I4) --------------------------------------------------------------------------------

_SELFTEST_DOC = """---
id: demo-task
status: active
depends_on: [amont]
epic: ROADMAP-demo
serves: [t-a, t-b]
blueprint: {id: some-gate, posture: applies}
template: [some-gate/step.md]
env: vault
---

# Objectif final

Corps.
"""


def selftest() -> None:
    """Vérifie extraction / verdict blueprint / assemblage sur du frontmatter in-memory (aucun I/O)."""
    slots = extract_stamp(_SELFTEST_DOC)
    assert slots["epic"] == "ROADMAP-demo", slots
    assert slots["serves"] == ["t-a", "t-b"], slots
    assert slots["blueprint"] == {"id": "some-gate", "posture": "applies"}, slots
    assert slots["template"] == ["some-gate/step.md"], slots

    # task sans slots STAMP → vides honnêtes (pas de faux-positif).
    empty = extract_stamp("---\nid: e\nstatus: active\n---\ncorps\n")
    assert empty["epic"] is None and empty["serves"] == [] and empty["blueprint"] is None, empty

    # verdict blueprint : défaut délégué (non résolu, raison honnête).
    v_default = _blueprint_verdict(slots["blueprint"], None)
    assert v_default is not None and v_default["resolved"] is False and v_default["reason"], v_default
    # seam injecté qui résout → resolved:true + champs fusionnés.
    v_ok = _blueprint_verdict(slots["blueprint"], lambda _bid: {"title": "Le gate"})
    assert v_ok is not None and v_ok["resolved"] is True and v_ok["title"] == "Le gate", v_ok
    # resolver qui ne trouve rien → liaison morte signalée, jamais inventée.
    v_dead = _blueprint_verdict(slots["blueprint"], lambda _bid: None)
    assert v_dead is not None and v_dead["resolved"] is False, v_dead

    # assemblage : axe injecté rendu tel quel.
    ctx = assemble_context("demo-task", slots, "surface-reseau-social", v_default)
    assert ctx["axis"] == "surface-reseau-social" and ctx["slug"] == "demo-task", ctx
    assert ctx["blueprint"]["resolved"] is False, ctx

    print("context.selftest: OK")


if __name__ == "__main__":
    selftest()
