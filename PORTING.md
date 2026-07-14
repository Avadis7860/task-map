# PORTING — journal d'extraction depuis le vault (état vivant)

`task-map` distille le moteur de graphe des tasks du vault en un package autonome, générique et empaqueté.
Ce fichier trace le port **couche par couche** : ce qui est extrait, ce qui reste au vault, le correctif de
généralisation appliqué.

## Source

- **Moteur à porter** : `.claude/scripts/lib/vault_tasks.py` du vault (`task-graph-v1`, READ-ONLY) — `classify`,
  DAG `depends_on`, phases d'épic, `SERVICES`/`CATEGORIES`.
- **Parseur frontmatter** : le vault utilise `lib/vault_content.split_frontmatter` → à réécrire **stdlib-pur
  interne** (le repo reste `dependencies=[]`).
- **Reste au vault** : les données (`.claude/tasks/`), le wrapper (`task_map.py`, P6), le hook `session-start`
  (P7), le manifeste north-star (données vault, P3).

## Design de référence

`corpus/decision/projects/2026-07-14--stamp-task-motor.md` (dans le vault) — coupe de frontière, modèle STAMP,
motor read+WRITE confiné, MCP link-by-reference, blueprint `deterministic-tooling-gate` appliqué.

## État par couche

| Couche | Phase | État |
|---|---|---|
| `core/roots` + `config` (socle) | P0 | **porté** (générique : marqueur `.taskmap.toml`/`.git`, env `TASKMAP_ROOT`) |
| CLI unifié (structure figée, stubs) | P0 | **porté** (squelette exécutable) |
| `frontmatter` (parseur stdlib-pur) | P1 | **porté** (remplace PyYAML ; parité prouvée sur 464 fichiers) |
| `graph` + `classify` (moteur) | P1 | **porté** (1:1 de `vault_tasks.py` ; READ-ONLY ; non-régression prouvée) |
| vocab externalisé (`.taskmap.toml`) | P2 | **porté** (vocab + `tasks_subdir` → config ; défauts permissifs ; parité re-prouvée) |
| manifeste north-star | P3 | à faire (données vault) |
| `authoring` (écriture STAMP) | P4 | à faire (gated par `stamp-write-model-reconcile`) |
| verbes `context`/`rollup`/`doctor` | P5 | à faire (+ résolution MCP du ref blueprint) |
| wrapper vault `task_map.py` | P6 | à faire (reste au vault) |
| rewire hook `session-start` | P7 | à faire (reste au vault) |
| backfill + adoption cockpit | P8 | à faire |

## Correctifs de généralisation appliqués

- **#1 — root-resolver dé-vaultisé** : `vault_root()` (cherchait `CLAUDE.md` + `.claude/`) → `project_root()`
  générique (marqueur `.taskmap.toml`/`.git`, env `TASKMAP_ROOT`, `--root`, fallback cwd). Jamais de
  `parents[N]` fixe.
- **#2 — moteur de graphe porté (P1)** : `vault_tasks.py` scindé en `graph.py` (chargement/DAG/phases/cycles/
  enfants/réconciliation) + `classify.py` (états/triggers/DoD/helpers de requête), avec **deux
  dé-vaultisations** :
  - le parsing frontmatter passe de PyYAML (`vault_content.split_frontmatter`) au parseur **stdlib-pur**
    `taskmap/frontmatter.py` (le repo reste `dependencies=[]`). Sous-ensemble YAML couvert : block-maps,
    block-seqs (`- x`, `- clé: v`), flow-seqs, scalaires typés (int/bool/null/**date→`datetime.date`**),
    chaînes quotées, commentaires, blocs `|`/`>` (littéral/folded + chomping). Hors-scope : ancres, multi-docs.
  - le chemin `.claude/tasks` en dur devient le paramètre `tasks_subdir` (défaut = disposition vault ;
    injection par config en P2). Le vocab (`PRIORITIES`/`SERVICES`/`CATEGORIES`) reste en constantes (P2).
- **#3 — vocab externalisé en config (P2)** : le vocab métier (`PRIORITIES`/`SERVICES`/`CATEGORIES`) et
  l'emplacement des buckets migrent de constantes de `graph.py` vers `taskmap/config.py` (`Config`, tables
  `[vocab]`/`[tasks]` de `.taskmap.toml`). `load_tasks(root, config=None)` résout `Config.load(root)`. Défauts
  **permissifs** (services/catégories vides ⇒ pas de validation) pour ne pas réprimander un repo tiers ; le
  vault déclare son vocab fermé dans son propre `.taskmap.toml` (mirroir de `vault_tasks.py`) → **parité
  conservée**. `_rank_key`/`_ready` reçoivent l'ordre des priorités en paramètre (plus de `PRIO` global). La
  carte épics→axes reste DÉLIBÉRÉMENT hors config (donnée north-star, un seul foyer → P3).

## Preuve de non-régression (P1 · re-vérifiée P2)

`tools/parity_check.py` compare, sur le corpus de tasks **réel** du vault, la sortie
`classify(load_tasks(root))` des deux moteurs — référence PyYAML (sous-process, venv scripts du vault) vs
candidat stdlib (in-process). **Verdict P1 (2026-07-14) : PARITÉ, diff vide sur 464 tasks** (records + warnings
identiques). **Re-vérifié P2 (2026-07-14) : PARITÉ, diff vide sur 465 tasks** — le moteur désormais
*config-driven* (lit `vault/.taskmap.toml`) reproduit toujours exactement le moteur vault hardcodé ; c'est la
preuve que l'externalisation du vocab n'a rien régressé (le +1 = la task-phase P1 archivée entre-temps). Ce
n'est pas un test pytest permanent (il exige le vault) ; le filet permanent est le corpus de fixtures
synthétique sous `tests/fixtures/vault/` (couvre trigger/phases/dod/épic/cycle/dangling/alias/hors-vocab, y
compris `any_of`/`all_of` absents du corpus vault mais portés par la grammaire) + `tests/test_config.py`.
