# Changelog

Format : [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/) · versionnage [SemVer](https://semver.org/lang/fr/).

## [Non publié]

### Ajouté (P1 — moteur de graphe porté)
- **`taskmap/frontmatter.py`** : parseur de frontmatter **stdlib-pur** (remplace PyYAML) — le repo reste
  `dependencies=[]`. Couvre le sous-ensemble YAML des tasks (maps, seqs, flow-seqs, scalaires typés
  int/bool/null/**date**, quotes, commentaires, blocs `|`/`>`). Parité des types calquée sur PyYAML 1.1.
- **`taskmap/graph.py`** : chargement des 3 buckets + DAG `depends_on` + dérivation des phases d'épic +
  détection de cycles + enfants d'épic + réconciliation des checklists. READ-ONLY. Chemin `.claude/tasks`
  paramétrable (`tasks_subdir`).
- **`taskmap/classify.py`** : machine à états (DONE/ACTIVE/READY/BLOCKED_DEPS/DEFERRED/EPIC/ERROR/CYCLE/
  CANCELLED) + prédicats `trigger` (grammaire fermée déterministe) + `dod_criteria` + helpers de requête
  (ready/tree_stats/burndown/wip/warnings/resettable). READ-ONLY, fail-soft conservateur.
- **API publique** re-exportée depuis `taskmap` : `load_tasks`, `classify`, `evaluate_trigger`,
  `evaluate_dod_criteria`, `ENGINE`.
- **Non-régression prouvée** (`tools/parity_check.py`) : sortie identique au moteur vault (`vault_tasks.py`)
  sur **464 tasks** réelles, diff vide. Filet permanent : fixtures synthétiques + `tests/test_frontmatter.py`
  / `test_graph.py` / `test_classify.py` (40 tests).

### Ajouté (P0 — bootstrap du repo)
- Squelette de repo autonome (package `src/taskmap/`, `pyproject.toml` hatchling src-layout, **cœur
  stdlib-pur** `dependencies=[]`, console `taskmap`).
- **CLI unifié** `taskmap` à structure **figée** : sous-commandes `context` / `link` / `unlink` / `rollup` /
  `doctor` câblées ; handlers en **stubs `NotImplementedError`** (avec pointeur de phase P4/P5) tant que le
  moteur n'est pas porté. `--version`, `--schema-version` (contrat **0.1.0**) et `--help` fonctionnent.
- **Enveloppe de sortie** figée (`{ok, schema_version}`, rc 0 pour lecture) + négociation de version — contrat
  inter-repos (`docs/schema-contract.md`).
- **Socle** : `core/roots.py` (résolution de racine générique par marqueur `.taskmap.toml`/`.git` + env
  `TASKMAP_ROOT`, jamais de `parents[N]` fixe) + `config.py` (`.taskmap.toml` via `tomllib`, défauts permissifs).
- **Docs** : `architecture.md` (protocole STAMP + couches + frontières délibérées) et `schema-contract.md`
  (enveloppe de sortie + négociation).
- **`.claude/` auto-travaillable** : skills `work-loop` + `quality-gate`, hook `post-edit-check`, persona
  `tool-builder` → le repo est travaillable seul (clone → work-loop), sans centre de contrôle.
- Tests de fumée du squelette (`tests/test_skeleton.py`) : imports, parser figé, root-resolver (marqueur/env/
  fallback), config (défauts + lecture périmètre), **honnêteté des stubs** (chaque verbe lève
  `NotImplementedError`).

### En cours (port depuis le vault, phase par phase — cf. ROADMAP-task-map)
- **P2** externalisation du vocab en `.taskmap.toml` · **P3** manifeste north-star (axes + carte épics→axes) ·
  **P4** module `authoring` (écriture des slots STAMP, atomique, jamais de commit — gated) · **P5** logique CLI
  réelle (`context`/`rollup`/`doctor` + résolution MCP du ref blueprint) · **P6** wrapper vault · **P7** rewire
  du hook session-start · **P8** backfill + adoption cockpit.
