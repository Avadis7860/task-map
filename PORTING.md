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
| `graph` + `classify` (moteur) | P1 | à porter (+ parseur frontmatter stdlib-pur interne) |
| vocab externalisé (`.taskmap.toml`) | P2 | à faire |
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
