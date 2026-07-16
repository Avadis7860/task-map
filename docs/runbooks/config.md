# config — runbook (`.taskmap.toml` déclaratif, vocab + buckets)

`src/taskmap/config.py` — charge `.taskmap.toml` à la racine du repo cible ; absent → **défauts permissifs**.
`tomllib` stdlib → **zéro dépendance**. C'est ici que vit le vocab par défaut du moteur (P2) : le vocab métier
(`priorities`/`services`/`categories`) et l'emplacement des buckets tasks, externalisés depuis `graph.py`. Un
repo sans config tourne permissif (services/categories vides ⇒ aucune validation, aucun warning) ; le vault
déclare son vocab **fermé** dans son propre `.taskmap.toml` et garde ses avertissements.

## Config — le contrat de config résolu

`src/taskmap/config.py:29` · consommé par `graph.load_tasks`, `classify` (via `prio`), `context`.
Dataclass **frozen**. Champs : `include`/`exclude` (sous-arbres tasks), `tasks_subdir` (emplacement des 3
buckets, défaut `.claude/tasks`), `priorities` (vocab **ORDONNÉ** — requis par le ranking, jamais vide),
`services`/`categories` (vocab fermé ; **vide ⇒ permissif**), `northstar_manifest` (rel. root ; None ⇒ pas de
rollup d'axe). Défauts = comportement générique. Immuable → pas de dérive en cours de run.

## Config.load() — .taskmap.toml → Config (ou défauts)

`src/taskmap/config.py:46` · appelé par `cli._resolve` et chaque coquille de lecture.
Statique. Absent → `Config()` (défauts permissifs). Sinon parse le TOML, lit les tables `[perimeter]`/`[tasks]`/
`[vocab]`/`[northstar]`, surcharge champ par champ. Point d'entrée unique de la config — les couches n'accèdent
jamais au TOML directement.

## Config.prio — l'ordre de rang des priorités (source unique)

`src/taskmap/config.py:41` · propriété · consommée par `classify._ready` → `core.rank_key`.
`{P0:0, P1:1, …}` dérivé de `priorities`. **Source unique** de l'ordre de priorité pour tout le ranking (le
cœur générique reçoit ce dict via `prio`). Une priorité hors-vocab est rangée en dernier (fail-soft, cf.
`load_tasks`).

## Zones non détaillées

- `CONFIG_FILENAME`, `DEFAULT_*` : constantes triviales. C'est le patron dont docs-map/front-map/code-map sont
  les jumeaux (config déclarative par repo cible).
