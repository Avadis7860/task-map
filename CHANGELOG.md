# Changelog

Format : [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/) · versionnage [SemVer](https://semver.org/lang/fr/).

## [Non publié]

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
- **P1** moteur de graphe (`vault_tasks.py` → `taskmap/graph.py` + `classify.py`) + parseur frontmatter
  stdlib-pur interne + non-régression.
- **P2** externalisation du vocab en `.taskmap.toml` · **P3** manifeste north-star (axes + carte épics→axes) ·
  **P4** module `authoring` (écriture des slots STAMP, atomique, jamais de commit — gated) · **P5** logique CLI
  réelle (`context`/`rollup`/`doctor` + résolution MCP du ref blueprint) · **P6** wrapper vault · **P7** rewire
  du hook session-start · **P8** backfill + adoption cockpit.
