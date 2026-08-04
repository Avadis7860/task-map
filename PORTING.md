# PORTING — journal d'extraction depuis le vault (état vivant)

`task-map` distille le moteur de graphe des tasks du vault en un package autonome, générique et empaqueté.
Ce fichier trace le port **couche par couche** : ce qui est extrait, ce qui reste au vault, le correctif de
généralisation appliqué.

## Source

- **Moteur à porter** : `.claude/scripts/lib/vault_tasks.py` du vault (`task-graph-v1`, READ-ONLY) — `classify`,
  DAG `depends_on`, phases d'épic, `SERVICES`/`CATEGORIES`.
- **Parseur frontmatter** : le vault utilise `lib/vault_content.split_frontmatter` → à réécrire **stdlib-pur
  interne** (le repo reste `dependencies=[]`).
- **Reste au vault** : les données (`.claude/tasks/`, **+ le manifeste north-star `.claude/northstar.yaml`**,
  porté P3), le wrapper (`task_map.py`, P6), le hook `session-start` (P7). Le moteur, lui, sait **charger** ce
  manifeste (générique) mais ne le possède pas.

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
| manifeste north-star (loader/validateur) | P3 | **porté** (`northstar.py` : loader stdlib + prédicats purs + rollup ; donnée vault) |
| `authoring` (écriture STAMP) | P4 | **porté** (gate `stamp-write-model-reconcile` résolu ; `plan_edit` pur + `apply_edit` atomique ; jamais de commit) |
| verbes `context`/`rollup`/`doctor` + `link`/`unlink` | P5 | **porté** (deep-dive `taskmap-mcp-degradation-contract` résolu ; résolution blueprint **déléguée** + seam) |
| wrapper vault `task_map.py` | P6 | à faire (reste au vault) |
| rewire hook `session-start` | P7 | à faire (reste au vault) |
| backfill + adoption forgemaster | P8 | à faire |

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
- **#4 — manifeste north-star chargé, pas possédé (P3)** : le moteur gagne `taskmap/northstar.py` (loader
  stdlib via `frontmatter.load`, validateurs = prédicats purs, rollup `axis_for_epic` cardinalité-1, selftest)
  et la table `[northstar]` de config (`Config.northstar_manifest`, absent ⇒ pas de rollup). La **donnée**
  (`.claude/northstar.yaml`) et la **prose SoT** (`corpus/decision/meta/*north-star*`) restent au vault —
  SoT-and-derive (I1) : la prose narre, le YAML dérive, l'`axis` d'une task est dérivé (épic→axe), jamais
  stocké. Recadrage vault du même jour : la prose v2/v3 (substrat Proxmox) a été réalignée en une décision
  **north-star lightweight** avant projection (cf. `2026-07-14--framework-north-star-lightweight.md`).

- **#5 — authoring : le volet WRITE confiné (P4)** : nouveau module `taskmap/authoring.py` (le SEUL qui écrit)
  + port stdlib de l'idiome d'écriture atomique du vault en `taskmap/core/atomic.py`. Le gate
  `stamp-write-model-reconcile` est **résolu** (contrat dans la décision vault
  `2026-07-14--stamp-write-model-contract.md`). Choix de généralisation : **édition chirurgicale ligne-à-ligne**
  (le parseur `frontmatter` est lossy → un round-trip bruiterait le git), slots STAMP au **rang canonique**
  (après `depends_on`), **`axis` jamais écrit** (dérivé, I1), **séparation pur/impur** (`plan_edit(text)→EditPlan`
  pur testable in-memory + `selftest` ; `apply_edit(path, plan)` = seule I/O, atomique, no-op si inchangé),
  **jamais de commit** (le fichier dirty est le hand-off vers la couche git/forgemaster). Les verbes CLI `link`/
  `unlink` qui consomment ce moteur restent P5.

- **#6 — verbes de lecture + résolution blueprint déléguée (P5)** : nouveau module `taskmap/context.py`
  (`build_context`/`rollup_axis`/`doctor` + cœur pur `extract_stamp`/`assemble_context`/`selftest`) ; les 5
  stubs CLI câblés. Deux choix de généralisation : (a) **les slots STAMP sont re-parsés du frontmatter** — le
  moteur de graphe porté (`load_tasks`) ne retient que `depends_on`, donc `context` relit `epic`/`serves`/
  `unblocks`/`blueprint`/`template` via `frontmatter.split_frontmatter` ; `axis` reste **dérivé** (jamais lu).
  (b) **La résolution du `blueprint:` ref est DÉLÉGUÉE au consommateur MCP** (deep-dive
  `taskmap-mcp-degradation-contract` résolu, décision vault `2026-07-14--…`) : task-map émet le ref +
  `resolved:false` + raison honnête par défaut et expose un **seam d'injection** `resolve_blueprint`, mais ne
  compose **jamais** le MCP lui-même — il reste offline / stdlib-pur / sans secret (le consommateur, une session
  Claude ou le forgemaster, a déjà l'accès MCP). `link`/`unlink` consomment `authoring` (grammaire d'ancre
  `clé=valeur[:posture]`, `--dry-run`, `axis=` refusé).

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
