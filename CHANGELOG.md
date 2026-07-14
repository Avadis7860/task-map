# Changelog

Format : [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/) · versionnage [SemVer](https://semver.org/lang/fr/).

## [Non publié]

### Ajouté (P5 — verbes de lecture + résolution blueprint déléguée)
- **`taskmap/context.py`** *(neuf)* : les verbes de LECTURE de STAMP. `build_context(root, slug)` rend les 3
  liaisons (axe **dérivé** via `northstar.axis_for_epic` · épic servi/`serves`/`unblocks` · blueprint ref+verdict) ;
  `rollup_axis(root, name)` agrège les tasks dont l'axe dérivé == `name` ; `doctor(root)` sépare les **problèmes
  durs** (dep dangling/cycle, manifeste incohérent, intégrité STAMP → `ok:false`) des **warnings advisory**
  (hygiène tasks = matériel de remontée proactive, ne bascule pas `ok`). Cœur **pur** `extract_stamp` /
  `assemble_context` / `_blueprint_verdict` + `selftest()` in-module (I4).
- **Slots STAMP re-parsés du frontmatter** : le moteur de graphe (`load_tasks`) ne retient que `depends_on` ;
  `context` relit `epic`/`serves`/`unblocks`/`blueprint`/`template` via `frontmatter.split_frontmatter`. `axis`
  n'est **jamais lu**, seulement dérivé (I1).
- **Résolution du `blueprint:` ref DÉLÉGUÉE** au consommateur MCP (deep-dive `taskmap-mcp-degradation-contract`
  résolu, décision vault `2026-07-14--taskmap-mcp-degradation-contract.md`) : `resolved:false` + raison honnête
  **par défaut**, **seam d'injection** `resolve_blueprint` pour un consommateur programmatique. task-map ne
  compose **jamais** le MCP (offline / stdlib-pur / sans secret ; `dependencies=[]` tenu) — la session Claude (ou
  le cockpit), qui a déjà `.mcp.json`, résout.
- **CLI câblée** (`taskmap/cli.py`) : les 5 stubs `NotImplementedError` remplacés. `link`/`unlink` consomment
  `authoring` — grammaire d'ancre `clé=valeur[:posture]` (`epic=` · `blueprint=<id>:<posture>` · `serves=a,b` ;
  `axis=` **refusé**), flag **`--dry-run`** (diff sans écriture), écriture atomique **jamais committée**.
- **API publique** : `build_context`, `rollup_axis`, `doctor`, `extract_stamp` re-exportés depuis `taskmap`.
  `SCHEMA_VERSION` inchangé (`0.1.0` — ajouts **additifs** au payload, aucun retrait).
- Filet : `tests/test_context.py` + `tests/test_cli.py` (26 tests — extraction, axe dérivé + None honnête,
  blueprint délégué + seam injecté + resolver mort/qui casse, rollup, doctor durs vs advisory, `link`/`unlink`
  end-to-end via `main`, dry-run, idempotence, `axis=`/posture refusés, task absente). Gate vert
  (ruff/mypy/pytest **108**). `test_skeleton` : la garde « stubs honnêtes » devient « verbes câblés ».

### Ajouté (P4 — authoring : le volet WRITE de STAMP)
- **`taskmap/authoring.py`** *(neuf)* : pose/mute les slots STAMP (`epic`/`serves`/`unblocks`/`blueprint`/
  `template`) dans le frontmatter d'une task. Le gate `stamp-write-model-reconcile` est **résolu** (contrat dans
  la décision vault `2026-07-14--stamp-write-model-contract.md`). **Édition chirurgicale ligne-à-ligne** (jamais
  de yaml round-trip — le parseur est lossy, il bruiterait le git) : seules les lignes des slots mutés changent,
  corps/commentaires/styles préservés. Slots au **rang canonique** (après `depends_on`), formes calquées sur le
  style maison (scalaire / flow-seq / flow-map). **`axis` jamais écrit** (dérivé, I1 — `StampEdit` n'a aucun
  champ `axis`). **Séparation pur/impur (I4)** : `plan_edit(text, edit) -> EditPlan{new_text, changed, diff}`
  **pur** + `selftest()` in-module ; `apply_edit(path, plan)` = seule I/O, **atomique**, no-op si inchangé
  (**idempotence** par état-cible déclaratif). **Jamais de commit** (le fichier dirty est le hand-off git/cockpit).
- **`taskmap/core/atomic.py`** *(neuf)* : port stdlib-pur de l'idiome d'écriture atomique du vault (tempfile
  même-répertoire + `os.replace`, cible intacte sur échec). `dependencies=[]` tenu.
- **API publique** : `plan_edit`, `apply_edit`, `StampEdit`, `EditPlan` re-exportés depuis `taskmap`.
- Filet : `tests/test_authoring.py` (13 tests — rang canonique, préservation corps/commentaires/quoting, diff
  minimal, idempotence, union/retrait de listes, clear, `blueprint` + validation de posture, `axis`
  non-écrivable, frontmatter absent refusé, écriture atomique via `tmp_path`).
- **Curseur d'autonomie** (tranché humain) : **écrit par défaut, `--dry-run` prévisualise** (blast radius faible —
  vault git-tracké, jamais committé par le motor). Le câblage CLI `link`/`unlink` reste **P5**.

### Ajouté (P3 — manifeste north-star)
- **`taskmap/northstar.py`** *(neuf)* : charge + valide le **manifeste north-star** du repo cible (axes + carte
  épic→axe + gates + doctrine). `load_manifest(path)` → `Manifest` (dataclasses `Axis`/`Manifest`) via le
  parseur stdlib ; **validateurs = prédicats purs** (`validate` → liste d'erreurs : `epic.axis`/`also_serves`/
  `gate.judges` hors axes, axe dupliqué, épic sans axe — **lien mort signalé, jamais deviné**) ; rollup pur
  **`axis_for_epic`** (cardinalité 1 = axe primaire ; hors carte → `None` honnête) ; **`selftest()`** in-module.
- **`taskmap/frontmatter.py`** : entrée `load(text)` — parse un **doc YAML complet sans fences** (le manifeste)
  en réutilisant le parseur récursif interne. Zéro dépendance ajoutée (`dependencies=[]` tenu).
- **`taskmap/config.py`** : table **`[northstar]`** de `.taskmap.toml` → champ `Config.northstar_manifest`
  (chemin relatif à la racine ; absent ⇒ `None` ⇒ pas de rollup, dégradation honnête).
- **API publique** : `load_manifest`, `axis_for_epic`, `validate`, `Manifest` re-exportés depuis `taskmap`.
  `SCHEMA_VERSION` du contrat inchangé (`0.1.0`) — le manifeste porte son **propre** `schema_version` (`1.0`).
- Filet : `tests/test_northstar.py` (loader, flags, validateur de liens morts, rollup) + `tests/fixtures/
  northstar/{valid,broken}.yaml` + un cas `load` sans-fences dans `tests/test_frontmatter.py`.
- **SoT-and-derive (I1)** : la SoT reste la **prose** (`corpus/decision/meta/*north-star*` côté vault) ; le YAML
  en est la projection vérifiable. Le manifeste réel du vault valide **sans lien mort** (rollup + flags corrects).

### Ajouté (P2 — config générique du vocab)
- **`taskmap/config.py`** : le **vocab métier** (priorités ordonnées, services, catégories) et l'**emplacement
  des buckets** (`tasks_subdir`) sont externalisés en `.taskmap.toml` (tables `[vocab]`/`[tasks]`) — jusque-là
  codés en dur dans `graph.py`. Défauts **permissifs** : sans fichier, `services`/`categories` sont vides ⇒
  aucune validation ni warning (un repo tiers n'est jamais réprimandé pour un vocab non déclaré) ; `priorities`
  garde un défaut ordonné `P0…P3` (requis par le ranking). Propriété `Config.prio` = source unique de l'ordre.
- **`graph.py`/`classify.py` dé-vaultisés** : `load_tasks(root, config=None)` résout `Config.load(root)` ;
  `PRIORITIES`/`PRIO`/`SERVICES`/`CATEGORIES` retirés des constantes de module (déplacés en `config.py`). La
  validation service/category ne se déclenche que si le vocab est non vide. `_rank_key`/`_ready` reçoivent
  l'ordre des priorités en paramètre. **Records classifiés inchangés** (aucun champ neuf).
- **`Config`** ajouté aux re-exports publics. `SCHEMA_VERSION` inchangé (`0.1.0` — ni l'enveloppe ni la forme
  des records ne bougent).
- **Non-régression re-prouvée** : `tools/parity_check.py` reste **diff vide sur 465 tasks** vault, le vault
  ayant reçu un `.taskmap.toml` mirroir de son vocab. Filet : `tests/test_config.py` + test de généricité
  (`load_tasks(config=Config())` → aucun warning vocab) + fixture `.taskmap.toml`.

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
- **P6** wrapper vault `task_map.py` (compose la lib packagée) · **P7** rewire du hook session-start (consomme
  `taskmap context`) · **P8** backfill des slots STAMP + adoption cockpit + un vrai resolver MCP injecté côté
  consommateur.
