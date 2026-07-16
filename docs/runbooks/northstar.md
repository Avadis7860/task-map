# northstar — runbook (manifeste north-star : loader + validateur + rollup)

`src/taskmap/northstar.py` — charge + valide le manifeste north-star (projection de la SoT prose du repo
cible). Le manifeste (déclaré par `.taskmap.toml [northstar].manifest`, ex. `.claude/northstar.yaml`) encode
les **axes**, la **carte épic→axe** (rollup) et les **gates**. Chargé par le parseur stdlib de `frontmatter`
(zéro dépendance), validé par **prédicats purs** (I4) : un lien mort est **signalé, jamais deviné**.
SoT-and-derive (I1) : la prose narre, ce YAML dérive ; l'`axis` d'une task est dérivé, jamais stocké.

## parse_manifest() — dict brut → Manifest (tolérant, ne lève jamais)

`src/taskmap/northstar.py:52` · appelé par `load_manifest` et les selftests.
Construit un `Manifest` depuis le dict déjà parsé. **Tolérant** : champ absent → défaut sûr, entrée mal formée
**ignorée** (la validation, elle, signale les liens morts). Ne lève jamais. Résout `axes` (avec flags
`differentiator`/`underweighted`/`additive`), `epics` (`{axis, also_serves}`), `gates` (`{judges}`),
`doctrine`, `prose_sot`.

## load_manifest() — fichier YAML → Manifest

`src/taskmap/northstar.py:92` · appelé par `context._load_manifest`.
Lit le fichier à `path` (parseur stdlib `frontmatter.load`) puis `parse_manifest`. Fichier absent →
`FileNotFoundError` (l'appelant `_load_manifest` l'attrape → dégradation honnête, pas de rollup).

## validate() — prédicats purs → liste d'erreurs (vide = cohérent)

`src/taskmap/northstar.py:98` · appelé par `context.doctor`.
PUR, ne lève jamais. Liste **vide = cohérent**. Vérifie : ids d'axes uniques ; tout `epic.axis` et
`also_serves` ∈ axes ; tout `gate.judges` ∈ axes ; épic sans axe signalé. Chaque incohérence = une string
lisible → remontée par `doctor` en `problems` (dur).

## axis_for_epic() — le rollup pur épic → axe primaire

`src/taskmap/northstar.py:124` · appelé par `context.build_context`/`rollup_axis`.
Rend l'axe **primaire** (cardinalité 1) de l'épic, ou `None` s'il n'est pas dans la carte (honnête). C'est le
cœur qui matérialise « quel axe north-star sert cette task » sans stocker l'axe — dérivé à la volée depuis
l'épic.

## Axis / Manifest — les dataclasses résolues

`src/taskmap/northstar.py:26` (Axis) · `:37` (Manifest) · frozen.
`Axis` : `{id, order, differentiator, underweighted, additive}` (flags dry, pas de prose). `Manifest` :
`{schema_version, axes, epics, gates, doctrine, prose_sot}` + propriété `axis_ids` (frozenset). `MANIFEST_SCHEMA_VERSION`
(`:22`) est distinct du `SCHEMA_VERSION` de sortie taskmap.

## Zones non détaillées

- `selftest` (`:152`) + les fixtures `_SELFTEST_*` : preuve in-module (loader + flags + validateur + rollup sur
  deux docs mémoire). Le *pourquoi* des axes (v2/v3 north-star) : la prose `corpus/decision/meta/*north-star*`
  du repo cible (SoT).
