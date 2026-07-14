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

## Quels fichiers sont versionnés

taskmap **n'écrit pas d'index dérivé** (lecture live). Les seuls artefacts qu'il peut écrire (module `authoring`,
P4) sont les **slots STAMP dans le frontmatter des tasks** du vault cible — versionnés par le vault, jamais par
taskmap (qui ne commit jamais).
