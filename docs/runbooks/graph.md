# graph — runbook (chargement des buckets + DAG depends_on + phases)

`src/taskmap/graph.py` — la moitié **chargement + structure** du moteur `task-graph-v1` (port de
`vault_tasks.py`). Charge les 3 buckets `tasks/{backlog,active,archive}` en **live**, construit le DAG
`depends_on`, dérive les arêtes de phases d'une umbrella, réconcilie les checklists. READ-ONLY : n'écrit rien.
La classification d'état (triggers, DoD) vit dans `runbooks/classify.md`.

## load_tasks() — les 3 buckets → index {id: record} + warnings

`src/taskmap/graph.py:96` · appelé par `classify`, `build_context`, `rollup_axis`, `doctor`, CLI edit.
Entrées : `root`, `config` (None → `Config.load(root)`). rglob `tasks_subdir/{backlog,active,archive}/**/*.md`
(reorg V2 : découvre `backlog/<service>/*.md`, `_inbox/`). **Invariant d'ordre** : archive chargé en dernier
→ **done écrase** un même id en backlog (le statut terminal fait foi). Par task : `split_frontmatter`, dérive
`status` du bucket si absent (`BUCKET_DEFAULT_STATUS`), union `blocked_by`(déprécié)→`depends_on`, valide à la
frontière `env`/`service`/`category`/`priority` **fail-soft** (hors-vocab → warning + ignoré, jamais un crash ;
vocab vide ⇒ validation désactivée pour ne pas réprimander un repo tiers). **Exemption terminale** : le warning
`priority hors vocab` est tu sur une task `done`/`cancelled` — il annonce un effet d'ordonnancement qui ne la
concerne plus, donc un faux positif permanent ; critère = statut effectif, comme l'intégrité STAMP du doctor. Émet un record figé (id, status,
priority, depends_on, tags, env, service, category, trigger, dod_criteria, phases, phase_checklist, bucket,
path). Signale : slug≠id, frontmatter absent/illisible, incohérence bucket↔status, id dupliqué. Termine par
`derive_phase_deps` (arêtes de phases fusionnées dans l'index).

## derive_phase_deps() — les arêtes séquentielles d'une umbrella phasée

`src/taskmap/graph.py:206` · appelé en queue de `load_tasks`.
Augmente **in-mémoire** le `depends_on` des membres d'une umbrella depuis son manifeste `phases:` (liste
ordonnée d'étapes, chaque étape = liste d'ids parallèles). Chaque membre de l'étape N reçoit (union
dédupliquée, ordre stable) **tous les ids des étapes < N** ; les membres d'une même étape ne dépendent PAS
l'un de l'autre. **Union** avec les `depends_on` explicites (jamais d'écrasement) ; provenance notée dans
`rec['phase_deps']`. Fail-soft : un membre absent de l'index est signalé (warning), sans arête fautive.

## reconcile_epics() — checklist DoD prose ↔ status réel

`src/taskmap/graph.py:246` · appelé par `context.doctor` (advisory).
PUR, read-only. Confronte la checklist `- [x] **P<n> — `slug`**` d'une umbrella (`phase_checklist`) au status
RÉEL des sous-tasks. Trois cas → warning (dérive de PROSE ⇒ **toujours warn, jamais error**) : `[x]`+status≠done
(case en avance), `[ ]`+status==done (case en retard), slug listé sans fichier (non matérialisée). En prime :
un membre `phases:` en `cancelled` → warning (il bloquerait l'aval à vie).

## Zones non détaillées (signalées)

- `_normalize_phases` (`:60`), `_parse_phase_checklist` (`:86`), `_children` (`:226`), `_s` (`:55`) : helpers
  de normalisation/parsing internes, lisibles au fil du code. Le cœur générique du graphe (`detect_cycles`,
  `eff_prio`, rang) est **re-exporté** ici mais documenté dans `runbooks/core.md`. Le schéma du record :
  `docs/schema-contract.md`.
