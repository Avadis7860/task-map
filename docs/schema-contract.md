# Contrat de schéma (en cours de gel)

Ces schémas sont un **contrat inter-repos** : le hook `session-start` du vault et (à terme) le `cockpit` lisent
la sortie de `taskmap`. On peut faire évoluer un **moteur** interne sans changer le schéma ; changer un schéma
(retrait/renommage d'un champ figé) est un **breaking change** — bump de version + entrée CHANGELOG.

**Statut P0** : l'**enveloppe de sortie** + la **négociation de version** sont figées ci-dessous. Le **modèle
STAMP** (slots, vocab, cardinalités) et la forme JSON exacte de `context`/`rollup` sont renseignés en **P1/P5**,
quand le moteur de graphe et les verbes sont portés.

## Enveloppe de sortie, codes de retour & négociation de version

Chaque **verbe de lecture** (`context`, `rollup`, `doctor`) émet un objet JSON sous **enveloppe uniforme** :

```json
{ "ok": true, "schema_version": "0.1.0", "...": "charge utile du verbe" }
```

- **`ok`** (bool) : `true` = succès ; `false` = échec **logique** (task introuvable, liaison morte, axe non
  résolu) — accompagné de **`reason`** (message lisible). Un consommateur teste `ok`, jamais une clé d'erreur
  ad-hoc.
- **`schema_version`** : la version du contrat qui a produit ce payload (négociation — cf. ci-dessous).
- **Code de retour** : les verbes JSON sortent **rc 0**, y compris sur `ok:false`. Le succès **logique** se lit
  dans le corps (`ok`), pas dans `rc` — un `ok:false` n'est pas un crash. Un `rc ≠ 0` signale une **panne**
  (traceback, argv invalide), pas un résultat vide. Le consommateur parse le stdout JSON quel que soit rc.

**Négociation de version.** `taskmap --schema-version` imprime la version du contrat (ici `0.1.0`) et sort,
**sans lire aucune task** — un consommateur l'interroge pour (a) inclure `schema_version` dans sa clé de cache,
(b) vérifier la compatibilité majeure. La même valeur figure dans l'enveloppe de chaque verbe. Évolution
**additive** : incrément mineur quand on AJOUTE un slot/champ/valeur ; un consommateur d'une version antérieure
ignore simplement les nouveautés (jamais de retrait/renommage).

## `context <slug>` — les 3 liaisons STAMP d'une task *(figée P5)*

Rend pour une task son **axe** north-star (dérivé), l'**épic** servi + `serves`/`unblocks`, et le **blueprint**
appliqué (ref + verdict). Charge utile :

```jsonc
{
  "ok": true,
  "slug": "…",
  "axis": "…",                 // DÉRIVÉ : epic → manifeste.epics[epic].axis (jamais lu ni stocké ; null hors carte)
  "epic": "…",                 // épic servi (0..1) ; null si non lié
  "serves": ["…"], "unblocks": ["…"],
  "blueprint": { "id": "…", "posture": "applies|tests|updates-candidate",
                 "resolved": false, "reason": "…" },
  "template": ["…"],
  "schema_version": "0.1.0"
}
```

- **`axis`** est **dérivé** du rollup épic→axe (`northstar.axis_for_epic`) : jamais lu ni stocké (I1). `null` si
  la task n'a pas d'`epic`, si l'épic est hors carte, ou si aucun manifeste n'est configuré (**honnête**).
- **`blueprint`** est `null` si non lié. Sinon `{id, posture}` + un **verdict** : par **défaut**
  `resolved:false` + `reason` (« résolution déléguée au consommateur MCP ») — task-map **ne compose pas le
  MCP** ; il émet le ref (link-by-reference déterministe-local) et le **consommateur** (une session Claude qui a
  déjà `.mcp.json`, ou le cockpit) le résout via `read(type=blueprint, ref=<id>)`. Un consommateur programmatique
  peut injecter un resolver (seam `resolve_blueprint`) : un dict véridique → `resolved:true` (+ champs fusionnés) ;
  un vide/`empty:true` → **liaison morte signalée**, jamais inventée. Contrat : décision vault
  `corpus/decision/projects/2026-07-14--taskmap-mcp-degradation-contract.md`.

## `rollup axis <nom>` — agrégat d'un axe *(figée P5)*

```jsonc
{ "ok": true, "dimension": "axis", "name": "…", "count": 2,
  "members": [ { "slug": "…", "status": "…", "epic": "…" } ],
  "schema_version": "0.1.0" }
```

`members` = les tasks dont l'axe **dérivé** (épic→axe) == `name`, triées par slug. Pas de manifeste configuré, ou
axe inconnu → `ok:false` + `reason` (dégradation honnête, jamais un agrégat vide trompeur).

## `doctor` — cohérence des liaisons *(figée P5)*

```jsonc
{ "ok": false, "checked": 468,
  "problems": ["…"],   // incohérences DURES → bascule ok:false
  "warnings": ["…"],   // advisory (remontée proactive) → NE bascule PAS ok
  "schema_version": "0.1.0" }
```

- **`problems`** (chaînes lisibles) — les incohérences **structurelles** : dépendance fantôme (`dep dangling`),
  `cycle de dépendances`, manifeste north-star incohérent (`northstar.validate`), intégrité STAMP (épic hors
  carte ; blueprint mort **si** un resolver est fourni). `ok = not problems`.
- **`warnings`** — l'hygiène tasks déjà surfacée par le moteur (réconciliation ROADMAP, WIP, différés, vocab
  hors-liste) : du **matériel de remontée proactive**, pas des échecs — ne bascule jamais `ok`.
- **Code de retour** : `doctor` suit l'enveloppe taskmap (**rc 0**, verdict dans `ok`), pas un `rc≠0`.

## `link` / `unlink <slug> <ancre…>` — écriture des slots STAMP *(figée P5)*

Consomment `authoring` (P4) via le parseur **public** `taskmap.build_stamp_edit(tokens, *, removing)` (module
`taskmap/anchors.py`, re-exporté depuis `taskmap`) — un consommateur programmatique (le wrapper vault
`task_map.py`, P6) l'importe pour parser les ancres **à l'identique**, sans dupliquer la grammaire.
**Grammaire d'ancre** `clé=valeur[:posture]` :

| Ancre | `link` | `unlink` |
|---|---|---|
| `epic=<id>` | set l'épic | `epic` (nu) → vide le slot |
| `blueprint=<id>:<posture>` | set (posture ∈ applies/tests/updates-candidate) | `blueprint` (nu) → vide |
| `serves=a,b` / `unblocks=…` / `template=…` | **union** (ajout) | retire les items cités ; nu → vide la liste |
| `axis=…` | **refusé** (dérivé, non écrivable) | refusé |

`--dry-run` émet `{slug, dry_run:true, changed, diff}` **sans écrire** ; sinon `{slug, changed, applied}` après
écriture **atomique** (jamais de commit — le fichier dirty est le hand-off git/cockpit). Ancre invalide / posture
invalide / task absente → `ok:false` + `reason` (rc 0).

## Configuration du repo cible — `.taskmap.toml` *(P2)*

À la racine du repo cible, **facultatif**. Absent → **défauts permissifs** (le moteur tourne, sans validation de
vocab). Trois tables, toutes optionnelles ; manifeste **sec** (listes de noms / segments, zéro prose) :

```toml
[tasks]
subdir = [".claude", "tasks"]      # emplacement des 3 buckets (backlog/active/archive) sous la racine

[vocab]
priorities = ["P0", "P1", "P2", "P3"]              # ORDONNÉ (rang de tri) ; défaut P0…P3 (jamais vide)
services   = ["orchestrateur", "cockpit", "…"]    # vocab fermé ; ABSENT/VIDE ⇒ permissif (aucun warning)
categories = ["epic", "feature", "refactor", "…"] # idem : vide ⇒ permissif

[perimeter]                          # (posé P0, filtre dormant jusqu'à câblage ultérieur)
include = []
exclude = []
```

Sémantique des défauts : `priorities` porte un **ordre** requis par le ranking → défaut **non vide** (`P0…P3`),
un vocab hors liste est signalé puis rangé en dernier. `services`/`categories` sont **descriptifs** → défaut
**vide = permissif** : la validation ne se déclenche que si la liste est fournie. Le vault, lui, déclare son
vocab fermé pour conserver ses avertissements à l'identique (parité avec le moteur d'origine).

## Manifeste north-star — `.claude/northstar.yaml` *(P3)*

Donnée **du repo cible** (pas du moteur), pointée par `.taskmap.toml [northstar].manifest` (absent ⇒ pas de
rollup, dégradation honnête). C'est la **projection** de la SoT prose (les décisions north-star du repo) ;
manifeste **sec** (enums/flags/listes de noms, zéro prose). Chargé + validé par `taskmap/northstar.py`. Porte
son **propre** `schema_version` (ici `1.0`), distinct du `SCHEMA_VERSION` du contrat de sortie taskmap.

```yaml
schema_version: "1.0"
prose_sot: [<id-décision>, …]          # pointeurs vers la SoT narrative (traçabilité, non consommé par le rollup)
axes:
  - {id: <axe>, order: 1}                              # ORDONNÉ ; flags booléens optionnels ci-dessous
  - {id: <axe>, order: 3, differentiator: true, underweighted: true}
  - {id: <axe>, order: 4, additive: true}
epics:
  <ROADMAP-id>: {axis: <axe>}                          # axe PRIMAIRE (cardinalité 1, drive le rollup)
  <ROADMAP-id>: {axis: <axe>, also_serves: [<axe>, …]} # multi-axe documenté (informatif)
gates:
  <gate-id>: {judges: [<axe>, …]}                      # quels axes ce gate juge
doctrine: [<nom>, …]                                    # méthode transversale (pas un axe)
```

**Sémantique** : `axis_for_epic(epic)` = l'axe **primaire** de l'épic (rollup consommé par `context`/`rollup` en
P5), `None` si l'épic n'est pas dans la carte (**honnête**, jamais deviné). La carte ne liste que les epics
**vivants** ; le **statut** live est délégué au graphe, jamais figé ici. La **priorité** d'un épic n'est PAS
portée (SoT unique = son frontmatter). **Validation** (prédicats purs, `validate` → liste d'erreurs, vide =
cohérent) : ids d'axes uniques ; tout `epic.axis`/`also_serves`/`gate.judges` ∈ axes — un **lien mort est
signalé, jamais inventé**.

## Authoring — contrat d'écriture *(P4)*

Le module `authoring` est le **seul** qui écrit (volet WRITE de STAMP, confiné). Contrat (décision vault
`corpus/decision/projects/2026-07-14--stamp-write-model-contract.md`, deep-dive `stamp-write-model-reconcile`) :

- **Édition chirurgicale ligne-à-ligne**, jamais de yaml round-trip (le parseur `frontmatter` est *lossy* :
  drop commentaires/blancs, réécrit `|`/`>`, coerce les dates → re-dumper bruiterait le git). Seules les lignes
  des slots mutés changent ; corps, commentaires, styles et clés voisines restent intacts.
- **Slots STAMP** posés en bloc au **rang canonique**, juste après `depends_on`, dans l'ordre
  `epic · serves · unblocks · blueprint · template`. Formes : `epic: <id>` (scalaire) ;
  `serves`/`unblocks`/`template: [a, b]` (flow-seq ; vidé ⇒ ligne retirée) ;
  `blueprint: {id: <id>, posture: applies|tests|updates-candidate}` (flow-map). **`axis` : jamais écrit**
  (dérivé du rollup épic→axe, I1 ; `StampEdit` n'a structurellement aucun champ `axis`).
- **Séparation pur/impur (I4)** : `plan_edit(text, edit) -> EditPlan{new_text, changed, diff}` est **pur**
  (zéro I/O, `selftest` in-module). **Idempotence** : sémantique déclarative d'état-cible → `changed = new != old`,
  ré-appliquer = no-op. `apply_edit(path, plan)` est la **seule** coquille impure : écriture **atomique**
  (tempfile même-répertoire + `os.replace` — cible intacte sur interruption), no-op si `not changed`.
- **Jamais de commit** : le motor n'écrit que le fichier. Le fichier dirty non-committé **est** le point de
  hand-off vers la couche git/cockpit (worktree → gate → GO humain → `dev` ff → `main`). Un outil qui
  committerait entrerait en collision avec la doctrine writeback-post-merge-sous-GO du vault.
- **Curseur d'autonomie** (tranché humain 2026-07-14) : **écrit par défaut, `--dry-run` prévisualise** — le CLI
  (P5) fait `plan_edit` seul en dry-run (imprime `diff`), `plan_edit`+`apply_edit` sinon.

## Quels fichiers sont versionnés

taskmap **n'écrit pas d'index dérivé** (lecture live). Les seuls artefacts qu'il peut écrire (module `authoring`,
P4) sont les **slots STAMP dans le frontmatter des tasks** du vault cible — versionnés par le vault, jamais par
taskmap (qui ne commit jamais).
