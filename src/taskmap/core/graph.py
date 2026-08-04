"""core.graph — cœur de graphe GÉNÉRIQUE, data-shape-agnostique (stdlib-pur, zéro import taskmap).

Primitives de séquencement d'un DAG de tasks, consommables **cross-repo** : le vault les nourrit avec ses
records STAMP (`graph.load_tasks` → `classify`), un tiers (le forgemaster) les nourrit avec ses propres rows
projetés (SQLite). Le cœur ne connaît NI le markdown, NI les slots STAMP, NI le vocab métier — juste la forme
de record minimale ci-dessous. C'est le foyer public annoncé par `core/__init__` (« à enrichir au port du
moteur »).

**Record générique attendu** (dict) — les primitives lisent défensivement, un champ absent ne crashe pas :

  - `id: str`              — identité unique (clé de l'index) ; seul champ requis pour le rang.
  - `depends_on: list[str]`— arêtes sortantes (ids) ; absent ⇒ `[]` (task-feuille).
  - `priority: str`        — clé du vocab ordonné passé en `prio` ; hors-vocab ⇒ rang `len(prio)` (dernier).
  - `status: str`          — lu par `detect_cycles` uniquement via `depends_on` (pas le status) ; le status
                             sert au classifieur AMONT (`classify`), pas ici.
  - `created: str`         — date ISO pour le tiebreak ; absent/"" ⇒ `"9999-99-99"` (rangée en dernier).
  - `optional: bool`       — posé par le classifieur amont (`"optional" in tags`) ; absent ⇒ non-optionnel.

Deux apports par rapport au port vault d'origine :
  1. `detect_cycles` DÉPLACÉE ici (re-exportée par `taskmap.graph` pour la back-compat) ;
  2. **`eff_prio`** GRADUÉE depuis le fork forgemaster (`task-graph-v1` adapté) : la **priorité effective
     transitive** — une task de faible priorité qui débloque une task plus prioritaire remonte — devient le
     rang canonique des DEUX consommateurs (distillation-vers-le-centre).
"""
from __future__ import annotations

from collections.abc import Callable


def detect_cycles(index: dict[str, dict]) -> set[str]:
    """Membres d'un cycle de dépendances (DFS colorée ; arêtes dangling ignorées). Graphes petits."""
    color: dict[str, int] = {}   # 0 white / 1 grey / 2 black
    members: set[str] = set()

    def visit(u: str, path: list[str]) -> None:
        color[u] = 1
        path.append(u)
        for v in index[u].get("depends_on", []):
            if v not in index:
                continue
            if color.get(v, 0) == 1:          # back-edge → cycle
                if v in path:
                    members.update(path[path.index(v):])
            elif color.get(v, 0) == 0:
                visit(v, path)
        color[u] = 2
        path.pop()

    for t in index:
        if color.get(t, 0) == 0:
            visit(t, [])
    return members


def eff_prio(index: dict[str, dict], prio: dict[str, int]) -> dict[str, int]:
    """Priorité **effective transitive** : `eff(t) = min(rang propre, min sur dépendants transitifs)`.

    Une task de faible priorité qui débloque une task plus prioritaire remonte (gradué du fork forgemaster).
    `prio` = vocab ORDONNÉ (P0=0…) ; priorité hors-vocab ⇒ `len(prio)` (fail-soft, derrière tout le monde).
    `depends_on` lu en `.get(...)` (un record sans dépendances = task-feuille, eff == rang propre). Récursion
    sur les arêtes INVERSES (`dependents`), mémoïsée, garde de pile anti-cycle."""
    unknown = len(prio)
    dependents: dict[str, set[str]] = {sid: set() for sid in index}
    for sid, t in index.items():
        for d in t.get("depends_on", []):
            if d in index:
                dependents[d].add(sid)
    memo: dict[str, int] = {}

    def eff(sid: str, stack: frozenset[str]) -> int:
        if sid in memo:
            return memo[sid]
        best = prio.get(index[sid].get("priority", ""), unknown)
        for child in dependents[sid]:
            if child not in stack:
                best = min(best, eff(child, stack | {sid}))
        memo[sid] = best
        return best

    return {sid: eff(sid, frozenset()) for sid in index}


def rank_key(t: dict, effp: dict[str, int]) -> tuple:
    """Ordre total canonique : priorité effective ↑, optionnel après, création ↑, id (tiebreak, zéro ex-æquo).

    Pour un row forgemaster (`optional` toujours 0, `id`≡`slug`) le rang se réduit à `(eff, created, id)` —
    l'ordre du fork forgemaster PRÉSERVÉ. Pour le vault, gain de `eff_prio` sur l'ancien rang plat."""
    return (effp[t["id"]], 1 if t.get("optional") else 0, t.get("created") or "9999-99-99", t["id"])


def rank_ready(classified: dict[str, dict], prio: dict[str, int],
               scope_pred: Callable[[dict], bool] | None = None) -> list[dict]:
    """Tasks READY (dans `scope_pred`), triées par le rang canonique (`eff_prio` + tiebreaks). `scope_pred`
    None ⇒ toutes. `prio` = vocab ordonné (source unique du ranking). La tête = la NEXT dispatchable."""
    effp = eff_prio(classified, prio)
    pred = scope_pred if scope_pred is not None else (lambda _t: True)
    return sorted((t for t in classified.values() if t["state"] == "READY" and pred(t)),
                  key=lambda t: rank_key(t, effp))


def resolve_next(classified: dict[str, dict], prio: dict[str, int],
                 scope_pred: Callable[[dict], bool] | None = None) -> dict | None:
    """La prochaine task dispatchable (READY de plus haut rang), ou None si aucune READY dans `scope_pred`."""
    r = rank_ready(classified, prio, scope_pred)
    return r[0] if r else None
