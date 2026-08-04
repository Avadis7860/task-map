# Architecture de `task-map`

## Intention

Un CLI **déterministe** qui répond, pour une task du système de gestion du travail, à ses **liaisons STAMP** :
« quel **axe** north-star sert-elle ? », « quel **épic/backlog** sert-elle et débloque-t-elle ? », « quel
**blueprint** applique-t-elle / met-elle à l'épreuve / est-elle candidate à mettre à jour ? » — au lieu d'une
liste mtime plate sans ancrage. Pas de service, pas de base : un CLI qui lit les tasks **en live** et rend du
JSON stable, consommé par le hook `session-start` du vault et (à terme) le forgemaster.

Origine : distillation du moteur de graphe `vault_tasks.py` du vault (`classify`, DAG `depends_on`, phases
d'épic), rendu **générique** (aucun chemin en dur) et **empaqueté** (vrai package installable au lieu de scripts
câblés par `sys.path`). Le vault reste **consommateur** via un wrapper mince (`task_map.py`, porté en P6).

## STAMP — le protocole matérialisé

STAMP = la liaison vivante de toute task à ses ancrages, dans les deux sens :

- **Amont (capital)** : `blueprint` (+ `posture` : applies | tests | updates-candidate) · `template`.
- **Aval (travail)** : `axis` (dérivé de l'épic) · `epic` servi · `serves` / `unblocks`.

Le rollup `task.epic → manifeste.epics[epic].axis` calcule l'axe north-star sans le stocker (pas de SoT
dupliquée). Le modèle de données figé (slots, cardinalités, vocab) est le **contrat** — cf.
`docs/schema-contract.md`.

## Les couches (de bas en haut)

```
                          taskmap.cli  (porte d'entrée unifiée : context / rollup / link / unlink / doctor)
                                │
        ┌───────────────────────┼───────────────────────────────┐
        ▼                       ▼                                ▼
   context/rollup          authoring/            (résolution MCP du ref blueprint)
   (lecture des liaisons)  (écriture des slots STAMP,        [P5, intégration
        │                   confiné, jamais de commit — P4)   optionnelle, honnête]
        ▼
   graph + classify + frontmatter   (moteur porté de vault_tasks.py : DAG depends_on, phases
        │             d'épic, classification, parseur stdlib — P1, présent)
        ▼
   config + core/roots   (socle stdlib : .taskmap.toml + résolution de racine)
```

- **`core/` + `config`** (P0+P2, présent) — résolution de racine générique (`roots`, marqueur `.taskmap.toml`/
  `.git`, env `TASKMAP_ROOT`) + config déclarative (`.taskmap.toml`, `tomllib` stdlib). **P2** y externalise le
  **vocab métier** (priorités ordonnées, services, catégories) et l'**emplacement des buckets** (`tasks_subdir`),
  jusque-là codés en dur dans `graph.py`. Défauts **permissifs** : sans fichier, services/catégories sont vides
  ⇒ aucune validation ni warning (un repo tiers n'est jamais réprimandé pour un vocab non déclaré) ; le vault
  déclare son vocab FERMÉ dans son `.taskmap.toml` et garde ses avertissements. Zéro dépendance.
  - **`core/graph`** — le **cœur de graphe GÉNÉRIQUE** (stdlib-pur, zéro import taskmap), foyer public
    consommable **cross-repo** : `detect_cycles` (déplacée de `graph.py`, re-exportée pour la back-compat),
    **`eff_prio`** (priorité **effective transitive** : une task qui débloque plus prioritaire remonte) et le
    **rang canonique** `rank_key`/`rank_ready`/`resolve_next`. Ce cœur ne connaît ni markdown ni STAMP — juste
    une forme de record minimale (`id`/`depends_on`/`priority`/`created`/`optional`). Le vault le nourrit via
    `classify` ; un tiers (le forgemaster) le nourrit avec ses propres rows projetés → **une seule copie vivante du
    moteur, dé-fork par import runtime** au lieu d'un fork vendoré. `eff_prio` est **graduée** du fork forgemaster
    (distillation-vers-le-centre) : la bonne idée du fork monte dans le SoT.
- **`graph` + `classify` + `frontmatter`** (P1, présent) — port du moteur `vault_tasks.py`, scindé :
  - **`frontmatter`** parse le frontmatter YAML **en stdlib pur** (remplace PyYAML → le repo reste
    `dependencies=[]`) ; ne couvre que le sous-ensemble utilisé (maps, seqs, flow-seqs, scalaires typés
    dont dates→`datetime.date`, blocs `|`/`>`). Types calqués sur PyYAML 1.1.
  - **`graph`** charge les 3 buckets (live), construit le DAG `depends_on`, dérive les arêtes de phases
    d'épic, détecte les cycles, réconcilie les checklists. Chemin `.claude/tasks` paramétrable.
  - **`classify`** classe chaque task et évalue les prédicats `trigger` (réveil) / `dod_criteria` (clôture),
    grammaire fermée déterministe. Expose les helpers de requête (ready/burndown/tree_stats).

  Lecture seule, live. **Non-régression prouvée** par `tools/parity_check.py` (sortie identique au moteur
  vault sur le corpus réel — diff vide sur 464 tasks).
- **`northstar`** (P3, présent) — charge le **manifeste north-star** du repo cible (`.taskmap.toml
  [northstar].manifest`, ex. `.claude/northstar.yaml`) : **axes** + carte **épic→axe** (rollup) + **gates** +
  doctrine. Loader stdlib (`frontmatter.load`), **validateurs = prédicats purs** (lien mort signalé, jamais
  deviné), rollup **`axis_for_epic`** (cardinalité 1 = axe primaire), `selftest`. **SoT-and-derive** (I1) : la
  prose narre (décisions north-star du repo), ce YAML dérive ; l'`axis` d'une task est **dérivé**, jamais
  stocké. La carte ne liste que les epics **vivants** ; le statut est délégué au graphe (jamais figé).
- **`authoring`** (P4, **présent** ; gate `stamp-write-model-reconcile` résolu) — pose/mute les slots STAMP par
  **édition chirurgicale ligne-à-ligne** (jamais de yaml round-trip : le parseur est lossy → il bruiterait le
  git ; corps/commentaires/styles préservés). Slots au **rang canonique** (après `depends_on`), `axis` **jamais
  écrit** (dérivé, I1). Séparation **pur/impur** (I4) : `plan_edit(text, edit) → EditPlan` est pur (zéro I/O,
  `selftest` in-module) ; `apply_edit(path, plan)` est la seule coquille impure — écriture **atomique**
  (tempfile même-dir + `os.replace`), no-op si inchangé (idempotence), **jamais de commit** (le fichier dirty
  est le hand-off vers la couche git/forgemaster). Module séparé du moteur de lecture (confine l'écart read-only).
  Contrat : décision vault `2026-07-14--stamp-write-model-contract.md`. Les verbes CLI `link`/`unlink` = P5.
- **`context` / `rollup` / `doctor`** (P5, **présent**) — les verbes de lecture. `context <slug>` rend les 3
  liaisons STAMP (axe **dérivé** via `northstar.axis_for_epic` · épic servi/`serves`/`unblocks` · blueprint
  ref+posture) ; `rollup axis <nom>` agrège les tasks dont l'axe dérivé == `<nom>` ; `doctor` sépare les
  **problèmes durs** (dep dangling/cycle, manifeste incohérent, intégrité STAMP → bascule `ok:false`) des
  **warnings advisory** (hygiène tasks, matériel de remontée proactive). Les slots STAMP sont **re-parsés du
  frontmatter** (le moteur de graphe ne retient que `depends_on`) ; `axis` n'est jamais lu, seulement dérivé.
  **Résolution du `blueprint:` ref DÉLÉGUÉE** au consommateur MCP (une session Claude a déjà `.mcp.json`, ou le
  forgemaster) : `resolved:false` + raison honnête par défaut, **seam d'injection** `resolve_blueprint` pour un
  consommateur programmatique — task-map ne compose jamais le MCP (offline / stdlib-pur / sans secret ; contrat
  `2026-07-14--taskmap-mcp-degradation-contract.md`). `link`/`unlink` consomment `authoring` (P4).

## Frontières délibérées (ce que ce repo n'est PAS)

- **Pas d'index dérivé bâti** (divergence assumée vs code-map). Le corpus tasks est minuscule et lu **en live**
  (comme bundle_map lit ses manifestes) → **pas de `build`, pas de `--out`, pas de garde index-absent**. La
  fraîcheur-par-hash d'un index (invariant I2 de la famille) ne s'applique donc pas aux lectures.
- **Pas de recopie du corpus capital.** Les blueprints/templates vivent dans le dépôt de données monté par
  le serveur, servis **uniquement** par le MCP `forgemaster-catalogs` — jamais recopiés ici. taskmap stocke
  un **ref** (link-by-reference, déterministe-local)
  et le **résout** via le MCP en P5 — intégration **optionnelle à dégradation honnête** (MCP down → utile sur
  les liens locaux, dit que le blueprint n'est pas atteignable, jamais inventé). Jamais une dépendance dure.
- **Pas de git, jamais.** Aucun shell-out git : ni pour la fraîcheur (lecture live), ni pour l'écriture
  (`authoring` écrit le fichier, un humain/le forgemaster commit).

## CLI unifié

Un seul `taskmap` avec des sous-commandes : `context <slug>` (les 3 liaisons), `rollup axis <nom>` (agrégat),
`link`/`unlink` (écriture, P4), `doctor` (cohérence). Une commande, un `--root`, un `.taskmap.toml`. Enveloppe
de sortie et négociation de version : cf. `docs/schema-contract.md`.
