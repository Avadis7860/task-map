# cli — runbook (porte unifiée `taskmap` + enveloppe de sortie)

`src/taskmap/cli.py` — une commande, cinq sous-commandes (`context`/`link`/`unlink`/`rollup`/`doctor`), un
`--root`, un `.taskmap.toml`. La **structure argparse est figée dès P0** ; chaque handler délègue à sa couche.
Pas de `build` ni `--out` : le corpus tasks est lu **live** (pas d'index dérivé, contrairement à code-map).

## main() / build_parser() — la surface CLI figée

`src/taskmap/cli.py:149` (main) · `:107` (build_parser) · main = entrypoint console.
`build_parser` câble le parseur : `--version`, `--schema-version` (négociation de contrat), et un
**parent parser** portant `--root` **partagé par toutes** les sous-commandes → `taskmap context foo --root .`
marche (le `--root` peut venir après le verbe, forme naturelle). Chaque sous-parser `set_defaults(func=…)` ;
`main` parse puis appelle `a.func(a)`. Sous-commandes : `context <slug>`, `link/unlink <slug> <ancre…>`
(`--dry-run`), `rollup axis <nom>`, `doctor`.

## _emit() — l'enveloppe uniforme {ok, schema_version}

`src/taskmap/cli.py:52` · appelé par tous les handlers.
Enveloppe **contrat inter-repos** : tout verbe de lecture porte `ok` (bool, défaut `True`) + `schema_version`.
Un payload qui pose déjà `ok:false` (échec logique : task introuvable, liaison morte) **l'emporte** sur le
défaut. **Invariant rc** : les verbes JSON sortent **rc 0** — le succès logique se lit dans le corps (`ok`),
jamais dans le code de retour (cf. `docs/schema-contract.md`). `SCHEMA_VERSION` importé de `taskmap.__init__`
(`:35` : évolution **additive**, bump mineur à l'ajout d'un champ/slot, jamais de retrait figé).

## _resolve() — (racine, config) pour toute sous-commande

`src/taskmap/cli.py:45` · appelé par chaque handler.
`roots.project_root(--root)` puis `Config.load(root)`. Pas d'`index_dir`/`--out` (lecture live). Point unique
de résolution : un handler reçoit toujours `(root, cfg)` prêts.

## _cmd_context / _cmd_rollup / _cmd_doctor — les verbes de lecture

`src/taskmap/cli.py:64` / `:69` / `:74` · `set_defaults(func=…)`.
Coquilles minces : résolvent `(root, cfg)`, délèguent à `context.build_context` / `rollup_axis` / `doctor`,
émettent sous enveloppe. Toute la logique vit dans `runbooks/context.md`.

## _cmd_link / _cmd_unlink / _run_edit — les verbes d'écriture (gated)

`src/taskmap/cli.py:79` / `:84` (délèguent) · `:88` (`_run_edit`, cœur partagé).
`_run_edit` charge l'index (résout le chemin de la task), fabrique le `StampEdit` via
`anchors.build_stamp_edit` (`removing` = link/unlink), calcule le **plan pur** (`plan_edit`), puis :
`--dry-run` → émet `{changed, diff}` sans écrire ; sinon `apply_edit` (écriture **atomique**, jamais de
commit). Task absente / ancre invalide (`AuthoringError`) → `ok:false` (rc 0). Détail : `runbooks/authoring.md`.

## _SchemaVersionAction — négociation de contrat

`src/taskmap/cli.py:32` · action argparse de `--schema-version`.
Imprime `SCHEMA_VERSION` et sort (comme `--version` mais pour l'inter-repos). Un consommateur (hook
session-start, forgemaster) l'interroge pour câbler sa clé de cache / vérifier la compat **avant** tout appel.

## Zones non détaillées

- `if __name__ == "__main__"` : trivial. Le contrat de sortie complet (formes de `context`, négociation de
  version) : `docs/schema-contract.md`.
