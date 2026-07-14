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

## `context <slug>` — les 3 liaisons STAMP d'une task *(forme figée en P5)*

Cible (le critère binaire de la mission) : rendre pour une task son **axe** north-star, l'**épic** servi/débloqué
et le **blueprint** appliqué. Esquisse de la charge utile (à geler en P5) :

```jsonc
{
  "ok": true,
  "slug": "…",
  "axis": "…",                 // dérivé : epic → manifeste.epics[epic].axis (non stocké)
  "epic": "…",                 // épic servi (0..1)
  "serves": ["…"], "unblocks": ["…"],
  "blueprint": { "id": "…", "posture": "applies|tests|updates-candidate", "resolved": true },
  "template": ["…"],
  "schema_version": "0.1.0"
}
```

Un `blueprint.id` qui ne résout pas via le MCP est une **liaison morte signalée** (`resolved:false` + raison),
jamais inventée.

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

## Quels fichiers sont versionnés

taskmap **n'écrit pas d'index dérivé** (lecture live). Les seuls artefacts qu'il peut écrire (module `authoring`,
P4) sont les **slots STAMP dans le frontmatter des tasks** du vault cible — versionnés par le vault, jamais par
taskmap (qui ne commit jamais).
