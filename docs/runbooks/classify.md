# classify — runbook (classification d'état + grammaire trigger/dod)

`src/taskmap/classify.py` — la moitié **état** du moteur `task-graph-v1`. Depuis l'index+DAG de `graph.py`,
classe chaque task, évalue les déclencheurs (`trigger`, réveil) et les critères de DoD (`dod_criteria`,
clôture) — **deux grammaires fermées déterministes DISJOINTES** — et expose les helpers de requête (ready,
burndown, stats). PUR + fail-soft : défaut **conservateur** (un trigger douteux ⇒ DEFERRED, jamais promu READY
en silence). Aucune écriture disque.

## classify() — chaque task → un état

`src/taskmap/classify.py:141` · appelé par `context.doctor`, le CLI (via `_ready`), les consommateurs.
Entrées : `index`, `root`/`today` (activent l'évaluation des `trigger`). Détecte d'abord les cycles
(`detect_cycles`), puis par task rend un état parmi DONE / CANCELLED / ACTIVE / BLOCKED (status direct) ·
EPIC (calcule `epic_closable` + blockers depuis les enfants non-optionnels) · ERROR (dep sans fichier) ·
CYCLE · READY / BLOCKED_DEPS (selon deps non-done). **Invariant clé** : une task READY qui porte un `trigger`
non franchi bascule **DEFERRED** (+ `defer_reason`) — sans `root`, les prédicats filesystem ne sont pas
évaluables ⇒ DEFERRED conservateur. Sortie : record enrichi `{**t, state, blockers, optional}`.

## evaluate_trigger() — le prédicat de réveil (grammaire fermée)

`src/taskmap/classify.py:40` · appelé par `classify` et réutilisé par `evaluate_dod_criteria`.
`(franchi, raison)`. **Défaut conservateur** : `None` ⇒ franchi ; prose / grammaire invalide / champ manquant /
glob non scopé / prédicat non vérifiable ⇒ `(False, raison)`. Prédicats : `glob_count` (op ∈ `>=`/`>`/`==`,
glob **anti-traversal** : `..`/absolu refusés), `task_done`, `path_exists` (scopé), `date_after` (`today`
injectable pour un test déterministe), `manual` (jamais auto-franchi). Composition un niveau : `any_of`/`all_of`.
Source unique de la grammaire filesystem, partagée avec la DoD.

## evaluate_dod_criteria() — les critères de clôture (composition ET)

`src/taskmap/classify.py:102` · appelé par `/task-close` (via le wrapper vault) et le cockpit.
`(tous_franchis, résultats[])`. READ-ONLY : tout verdict Tier-1.5 est **injecté** (`feature_verify_status`).
`criteria` en composition **ET**. Réutilise la grammaire déterministe de `evaluate_trigger` (les 4 prédicats
`DOD_DETERMINISTIC`) et ajoute `feature_verified` (lit un statut injecté : present∧fresh∧ok∧¬blocking).
**Défaut conservateur** : `None`/`[]` ⇒ `(True, [])` ; tout critère non évaluable ⇒ `ok=False` (jamais un
faux-vert). Un `when` non supporté en clôture → message pointant vers les prédicats valides ou la case prose.

## corroborate_done() — la politique de corroboration d'un done

`src/taskmap/classify.py:22` · appelé par le sweep de corroboration (preuves injectées).
PUR : applique la politique à des preuves **injectées** (l'I/O git/glob vit chez l'appelant). Deux axes
disjoints : **intégrité** (`corroborated` : archivé ∧ git-tracké — un manque = le statut ment → `gaps`) et
**distillation** (`distilled` : un post-mortem existe ? advisory ; un épic n'est jamais distillé →
`distilled=None`). L'état PR/merge GitHub est **délibérément exclu**.

## tree_stats() / burndown() — les compteurs de l'arbre

`src/taskmap/classify.py:206` (tree_stats) · `:253` (burndown) · appelés par les vues de progression.
PUR, filtrés par `scope`. `tree_stats` : `ready`/`blocked` (BLOCKED*+DEFERRED)/`done`. `burndown` :
`{done, total, ratio}` — **exclus du total** : CANCELLED, EPIC, ERROR/CYCLE (ratio 0.0 si total=0). Les états
hors seau sont surfacés ailleurs.

## is_resettable_state() / reset_block_reason() — éligibilité smart-reset

`src/taskmap/classify.py:241` / `:246` · appelés par le dispatch (cockpit).
PUR, source de vérité unique. Un (re-)dispatch n'est légitime **que** depuis READY (activable) ou DONE (refaire
un travail terminé) — `RESETTABLE_STATES`. Tout autre état (BLOCKED*, ACTIVE, CANCELLED, EPIC, ERROR, CYCLE) →
`reset_block_reason` rend un motif lisible du refus.

## section() — extraction d'une section markdown de niveau 1

`src/taskmap/classify.py:294` · utilitaire de lecture du corps d'une task.
Texte d'une section `# <heading>` jusqu'au prochain `# ` ; `''` si absente ; comparaison insensible
casse/espaces.

## Zones non détaillées

- `_in_scope` (`:184`, filtre `env:`/préfixe anti-traversal), `_ready` (`:198`, adaptateur vers
  `core.rank_ready`), `_wip`/`_warnings`/`_slim` : helpers de requête/format. Le rang canonique
  (`eff_prio`) : `runbooks/core.md`.
