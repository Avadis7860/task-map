"""classify — classification d'état + prédicats de réveil/clôture (READ-ONLY). Port de `vault_tasks.py`.

Moitié « état » du moteur `task-graph-v1` : à partir de l'index+DAG de `graph.py`, classe chaque task
(DONE/CANCELLED/ACTIVE/BLOCKED/EPIC/READY/BLOCKED_DEPS/DEFERRED/ERROR/CYCLE), évalue les déclencheurs
(`trigger`, grammaire fermée déterministe) et les critères de DoD machine-vérifiables (`dod_criteria`), et
expose les helpers de requête (ready, burndown, tree_stats, wip, warnings, resettable) consommés par le CLI
(câblés en P5). PUR + fail-soft (défaut CONSERVATEUR : trigger douteux ⇒ DEFERRED, jamais promu READY en
silence). Aucune écriture disque.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from taskmap.config import DEFAULT_PRIO
from taskmap.core.graph import detect_cycles, rank_ready  # cœur générique (cycles + rang canonique eff_prio)
from taskmap.graph import ROADMAP_PREFIX, SAFE_ENV, _children

TRIGGER_OPS = (">=", ">", "==")              # opérateurs autorisés de `glob_count`


def corroborate_done(rec: dict, *, archived: bool, git_tracked: bool, post_mortem: bool,
                     is_epic: bool = False) -> dict:
    """PUR, testable. Applique la POLITIQUE de corroboration d'un `status: done` à des preuves INJECTÉES
    (l'I/O — git, glob — vit chez l'appelant). DEUX AXES DISJOINTS : **intégrité** (`corroborated` : archivé
    ET git-tracké — un manque = le statut ment → `gaps`) et **distillation** (`distilled` : un post-mortem
    existe-t-il ? advisory, ne casse pas la corroboration ; un épic n'est jamais distillé → `distilled=None`).
    L'état PR/merge GitHub est délibérément EXCLU. Retourne {id, corroborated, distilled, evidence, gaps}."""
    gaps: list[str] = []
    if not archived:
        gaps.append("pas dans archive/ (status done mais bucket ≠ archive)")
    if not git_tracked:
        gaps.append("fichier non git-tracké (done non commité)")
    return {"id": rec["id"], "corroborated": not gaps,
            "distilled": None if is_epic else post_mortem,
            "evidence": {"archived": archived, "git_tracked": git_tracked, "post_mortem": post_mortem},
            "gaps": gaps}


def evaluate_trigger(trig, root: Path | None, index: dict[str, dict],
                     today: str | None = None) -> tuple[bool, str]:
    """(franchi, raison). Déterministe, read-only. Grammaire FERMÉE. Défaut conservateur : `None` ⇒ franchi ;
    prose / grammaire invalide / champ manquant / glob non scopé / prédicat non vérifiable ⇒ (False, raison).
    Prédicats : glob_count · task_done · path_exists · date_after · manual ; composition un niveau :
    any_of / all_of. `today` injecté pour un test déterministe (None → date système)."""
    if trig is None:
        return True, "aucun trigger"
    if isinstance(trig, str):
        return False, "trigger en prose non évaluable (migrer vers grammaire structurée)"
    if not isinstance(trig, dict):
        return False, f"grammaire invalide (type {type(trig).__name__})"
    if "any_of" in trig:
        subs = trig["any_of"]
        if not isinstance(subs, list):
            return False, "any_of: liste attendue"
        return (any(evaluate_trigger(s, root, index, today)[0] for s in subs), "any_of")
    if "all_of" in trig:
        subs = trig["all_of"]
        if not isinstance(subs, list):
            return False, "all_of: liste attendue"
        return (all(evaluate_trigger(s, root, index, today)[0] for s in subs), "all_of")
    when = trig.get("when")
    if when == "glob_count":
        glob, op, val = trig.get("glob"), trig.get("op"), trig.get("value")
        if not (isinstance(glob, str) and op in TRIGGER_OPS and isinstance(val, int)):
            return False, "glob_count: champs invalides (glob:str, op:>=/>/==, value:int)"
        if ".." in glob or glob.startswith("/"):
            return False, "glob_count: glob non scopé (.. ou absolu interdit)"
        if root is None:
            return False, "glob_count: root non fourni → non évaluable"
        n = sum(1 for _ in root.glob(glob))
        ok = n >= val if op == ">=" else n > val if op == ">" else n == val
        return ok, f"glob_count: {n} {op} {val}"
    if when == "task_done":
        tid = trig.get("id")
        if not isinstance(tid, str):
            return False, "task_done: id:str attendu"
        return (index.get(tid, {}).get("status") == "done"), f"task_done: {tid}"
    if when == "path_exists":
        path = trig.get("path")
        if not isinstance(path, str) or ".." in path or path.startswith("/"):
            return False, "path_exists: path non scopé"
        if root is None:
            return False, "path_exists: root non fourni → non évaluable"
        return ((root / path).exists()), f"path_exists: {path}"
    if when == "date_after":
        d = trig.get("date")
        if not isinstance(d, str):
            return False, "date_after: date:str ISO attendue"
        now = today if today is not None else date.today().isoformat()
        return (now >= d), f"date_after: {d} (today={now})"
    if when == "manual":
        return False, "manual: jamais auto-franchi (bascule humaine)"
    return False, f"when inconnu: {when!r}"


# Prédicats de DoD MACHINE-vérifiables (clôture). DISJOINT de `trigger` (réveil). Les 4 déterministes
# réutilisent la grammaire de `evaluate_trigger` (source unique) ; `feature_verified` LIT un verdict INJECTÉ.
DOD_DETERMINISTIC = ("glob_count", "path_exists", "task_done", "date_after")


def evaluate_dod_criteria(criteria, root: Path | None, index: dict[str, dict], *,
                          feature_verify_status=None, today: str | None = None) -> tuple[bool, list[dict]]:
    """(tous_franchis, résultats[]). READ-ONLY (tout verdict Tier-1.5 est INJECTÉ). `criteria` = prédicats en
    composition ET. Réutilise la grammaire de `evaluate_trigger` (glob_count/path_exists/task_done/date_after)
    et ajoute `feature_verified` (statut injecté). Défaut conservateur : `None`/`[]` ⇒ (True, []) ; tout
    critère non évaluable ⇒ `ok=False` (jamais un faux-vert)."""
    if criteria is None or criteria == []:
        return True, []
    if not isinstance(criteria, list):
        return False, [{"ok": False, "when": None,
                        "reason": f"dod_criteria: liste attendue (reçu {type(criteria).__name__})"}]
    results: list[dict] = []
    for crit in criteria:
        if not isinstance(crit, dict):
            results.append({"ok": False, "when": None, "reason": "critère: dict attendu"})
            continue
        when = crit.get("when")
        if when == "feature_verified":
            if feature_verify_status is None:
                results.append({"ok": False, "when": when,
                                "reason": "feature_verified: statut non injecté → non évaluable"})
                continue
            st = feature_verify_status(root) or {}
            ok = bool(st.get("present") and st.get("fresh") and st.get("ok") and not st.get("blocking"))
            results.append({"ok": ok, "when": when,
                            "reason": (f"feature_verified: present={st.get('present')} "
                                       f"fresh={st.get('fresh')} ok={st.get('ok')} "
                                       f"blocking={st.get('blocking')}")})
        elif when in DOD_DETERMINISTIC:
            ok, reason = evaluate_trigger(crit, root, index, today)
            results.append({"ok": ok, "when": when, "reason": reason})
        else:
            results.append({"ok": False, "when": when,
                            "reason": f"dod: prédicat non supporté en clôture ({when!r}) — "
                                      "laisser en case prose, ou utiliser "
                                      f"{(*DOD_DETERMINISTIC, 'feature_verified')}"})
    return all(r["ok"] for r in results), results


def classify(index: dict[str, dict], root: Path | None = None,
             today: str | None = None) -> dict[str, dict]:
    """Classe chaque task. `root`/`today` activent l'évaluation des `trigger` (READY → DEFERRED si non
    franchi). Sans `root`, les prédicats filesystem ne sont pas évaluables ⇒ DEFERRED conservateur."""
    cyc = detect_cycles(index)
    out: dict[str, dict] = {}
    for tid, t in index.items():
        s, deps, tags = t["status"], t["depends_on"], t["tags"]
        missing = [d for d in deps if d not in index]
        blockers: list[str] = []
        rec = {**t, "optional": "optional" in tags}
        if s == "done":
            state = "DONE"
        elif s == "cancelled":
            state = "CANCELLED"
        elif s == "active":
            state = "ACTIVE"
        elif s == "blocked":
            state = "BLOCKED"
        elif "epic" in tags or tid.startswith(ROADMAP_PREFIX):
            state = "EPIC"
            kids = _children(index, tid)
            non_opt = [k for k in kids if "optional" not in k["tags"]]
            rec["epic_closable"] = bool(non_opt) and all(k["status"] == "done" for k in non_opt)
            blockers = [f"{k['id']} ({k['status']})" for k in non_opt if k["status"] != "done"]
        elif missing:
            state, blockers = "ERROR", [f"{d} (AUCUN FICHIER TASK)" for d in missing]
        elif tid in cyc:
            state = "CYCLE"
        else:
            unmet = [d for d in deps if index[d]["status"] != "done"]
            state = "READY" if not unmet else "BLOCKED_DEPS"
            blockers = [f"{d} ({index[d]['status']})" for d in unmet]
            if state == "READY" and t.get("trigger") is not None:
                met, reason = evaluate_trigger(t["trigger"], root, index, today)
                if not met:
                    state = "DEFERRED"
                    rec["defer_reason"] = reason
        rec["state"], rec["blockers"] = state, blockers
        out[tid] = rec
    return out


def _in_scope(t: dict, scope: str | None) -> bool:
    """Filtre de portée du resolver. `scope` : None → toute task ; `env:<name>` → tasks du projet <name>
    (orchestrateur = env vide/`vault`), <name> kebab-validé (garde anti-traversal) ; sinon → préfixe d'id.
    Une portée typée inconnue/invalide ne matche RIEN (jamais une fuite ni un traversal)."""
    if scope is None:
        return True
    key, sep, val = scope.partition(":")
    if not sep:                                    # pas de `:` → préfixe d'id (rétro-compat)
        return t["id"].startswith(scope)
    if key == "env" and SAFE_ENV.fullmatch(val):
        return (t["env"] or "vault") == val        # orchestrateur : env vide ≡ `vault`
    return False                                   # portée typée inconnue/invalide → aucun match


def _ready(classified: dict[str, dict], scope: str | None,
           prio: dict[str, int] = DEFAULT_PRIO) -> list[dict]:
    """Tasks READY dans `scope`, triées par le rang canonique du cœur (`eff_prio` + tiebreaks). `prio` =
    ordre issu de la config (défaut P0…P3). Adaptateur mince : traduit le `scope` STAMP en prédicat, délègue
    le rang à `taskmap.core.graph.rank_ready` (source unique, partagée avec le consommateur cockpit)."""
    return rank_ready(classified, prio, scope_pred=lambda t: _in_scope(t, scope))


def tree_stats(classified: dict[str, dict], scope: str | None = None) -> dict[str, int]:
    """Compteurs de l'arbre de tasks (dans `scope`) : `ready` (activables), `blocked` (BLOCKED/BLOCKED_DEPS/
    DEFERRED), `done` (DONE). Les autres états sont hors seau (ACTIVE surfacé ailleurs ; EPIC/CANCELLED pas du
    burndown ; ERROR/CYCLE en warnings). PUR."""
    out = {"ready": 0, "blocked": 0, "done": 0}
    for t in classified.values():
        if not _in_scope(t, scope):
            continue
        st = t["state"]
        if st == "READY":
            out["ready"] += 1
        elif st == "DONE":
            out["done"] += 1
        elif st in ("BLOCKED", "BLOCKED_DEPS", "DEFERRED"):
            out["blocked"] += 1
    return out


# --- éligibilité « smart reset » du dispatch -------------------------------------------------------------
# Un (re-)dispatch n'est légitime que depuis READY (activable) ou DONE (refaire un travail terminé). JAMAIS
# depuis un état bloqué/différé/en-cours/terminal-annulé/épic/erreur. Source de vérité unique.
RESETTABLE_STATES = frozenset({"READY", "DONE"})

_RESET_BLOCK_REASONS = {
    "BLOCKED": "task bloquée — non réinitialisable",
    "BLOCKED_DEPS": "dépendances non levées — non réinitialisable",
    "DEFERRED": "en attente d'un déclencheur — non réinitialisable",
    "ACTIVE": "travail en cours — non réinitialisable",
    "CANCELLED": "task annulée — non réinitialisable",
    "EPIC": "épic (jamais dispatchée) — non réinitialisable",
    "ERROR": "graphe de dépendances cassé — non réinitialisable",
    "CYCLE": "cycle de dépendances — non réinitialisable",
}


def is_resettable_state(state: str) -> bool:
    """PUR : l'état autorise-t-il un reset du verrou de dispatch ? Seuls READY et DONE."""
    return state in RESETTABLE_STATES


def reset_block_reason(state: str) -> str | None:
    """PUR : motif lisible pour lequel `state` n'est PAS réinitialisable (None si l'état l'est)."""
    if is_resettable_state(state):
        return None
    return _RESET_BLOCK_REASONS.get(state, "état non réinitialisable")


def burndown(classified: dict[str, dict], scope: str | None = None) -> dict[str, float]:
    """Burndown de l'arbre (dans `scope`) : `done`, `total` (READY+BLOCKED+BLOCKED_DEPS+DEFERRED+ACTIVE+DONE),
    `ratio` (done/total, 0.0 si total=0). EXCLUS de `total` : CANCELLED, EPIC, ERROR/CYCLE. PUR."""
    done = total = 0
    for t in classified.values():
        if not _in_scope(t, scope):
            continue
        st = t["state"]
        if st == "DONE":
            done += 1
            total += 1
        elif st in ("READY", "BLOCKED", "BLOCKED_DEPS", "DEFERRED", "ACTIVE"):
            total += 1
    return {"done": done, "total": total, "ratio": round(done / total, 4) if total else 0.0}


def _wip(classified: dict[str, dict], scope: str | None) -> list[str]:
    """Avertissement de sérialisation du WIP, PAR PROJET (env). 1 ACTIVE/env = normal ; ≥2 sur un MÊME env →
    sérialisation intra-projet rompue. Orchestrateur = env vide ≡ `vault`."""
    by_env: dict[str, list[str]] = {}
    for t in classified.values():
        if t["state"] == "ACTIVE" and _in_scope(t, scope):
            by_env.setdefault(t["env"] or "vault", []).append(t["id"])
    return [f"WIP : {len(ids)} tasks ACTIVE sur l'env '{env}' ({', '.join(sorted(ids))}) "
            f"→ sérialiser (clore/débloquer avant d'en activer une autre dans ce projet)"
            for env, ids in sorted(by_env.items()) if len(ids) >= 2]


def _warnings(index_warns: list[str], classified: dict[str, dict], scope: str | None) -> list[str]:
    w = list(index_warns) + _wip(classified, scope)
    for t in classified.values():
        if _in_scope(t, scope):
            if t["state"] == "ERROR":
                w += [f"dep dangling : {t['id']} → {b}" for b in t["blockers"]]
            elif t["state"] == "CYCLE":
                w.append(f"cycle de dépendances : {t['id']}")
            elif t["state"] == "DEFERRED":
                w.append(f"différé (trigger non franchi) : {t['id']} → {t.get('defer_reason', '?')}")
    return w


def section(body: str, heading: str) -> str:
    """Texte d'une section `# <heading>` (titre niveau 1) jusqu'au prochain `# `. '' si absente. Comparaison
    insensible à la casse/aux espaces."""
    out: list[str] = []
    capture = False
    for ln in body.splitlines():
        if ln.startswith("# "):
            if capture:
                break
            capture = ln[2:].strip().lower() == heading.strip().lower()
            continue
        if capture:
            out.append(ln)
    return "\n".join(out).strip()


def _slim(t: dict) -> dict:
    out = {"id": t["id"], "state": t["state"], "priority": t["priority"],
           "depends_on": t["depends_on"], "blockers": t["blockers"],
           "resettable_state": is_resettable_state(t["state"])}
    if t["optional"]:
        out["optional"] = True
    if t.get("spawned_by"):
        out["spawned_by"] = t["spawned_by"]
    if "epic_closable" in t:
        out["epic_closable"] = t["epic_closable"]
    if t.get("defer_reason"):
        out["defer_reason"] = t["defer_reason"]
    return out
