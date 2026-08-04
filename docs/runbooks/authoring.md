# authoring — runbook (écriture chirurgicale des slots STAMP)

`src/taskmap/authoring.py` (+ `anchors.py`) — le volet **WRITE** de STAMP, écart délibéré vs le read-only de
la famille `-map`, **confiné** ici (module séparé du moteur de lecture). Contrat : décision vault
`2026-07-14--stamp-write-model-contract.md`. Invariants tenus : édition **ligne-à-ligne** (jamais de yaml
round-trip — le parseur est lossy, re-dumper bruiterait le git), **ordre canonique** du bloc STAMP après
`depends_on`, **`axis` jamais écrit** (dérivé, I1), **idempotence** (état-cible déclaratif), **séparation
pur/impur** (I4 : `plan_edit` pur, `apply_edit` seule coquille impure), **jamais de commit** (le fichier dirty
est le hand-off vers la couche git/forgemaster).

## build_stamp_edit() — grammaire d'ancre `clé=valeur[:posture]` → StampEdit

`src/taskmap/anchors.py:15` · appelé par `cli._run_edit` et le wrapper vault `task_map.py`.
PUR (échoue en `AuthoringError`). Parse les ancres : `epic=<id>` · `blueprint=<id>:<posture>` · `serves=a,b` ·
`unblocks=a` · `template=<bp>/<n>.md`. En unlink : `serves=a` retire `a` ; une ancre **nue** (`epic`,
`serves`) vide le slot (`clear`). `axis=…` est **refusé** (slot dérivé, non écrivable). Isolé de `cli` pour
être re-exportable sans import circulaire — le wrapper vault le consomme au lieu de dupliquer la grammaire.

## plan_edit() — le cœur pur : texte → EditPlan

`src/taskmap/authoring.py:94` · appelé par `cli._run_edit` · **zéro I/O**.
Calcule le texte-cible après application d'un `StampEdit`. Édition **chirurgicale** : ne réécrit que les
lignes des slots effectivement mutés (corps, commentaires, styles, clés voisines intacts). Parcourt
`_STAMP_SLOTS` dans l'ordre canonique → les insertions successives restent triées. `changed` = simple
`new != old` ; `diff` unifié si changé. Lève `AuthoringError` si pas de frontmatter `---…---` en tête ou non
terminé. **Idempotence** : ré-appliquer le même edit → `changed=False`.

## apply_edit() — la seule coquille impure

`src/taskmap/authoring.py:206` · appelé par `cli._run_edit` (hors `--dry-run`).
Écrit `plan.new_text` **atomiquement** (`core.atomic.write_text`) ; **no-op** (retourne False) si
`not plan.changed`. N'exécute **jamais** de git : le fichier dirty non-committé est le hand-off vers git/forgemaster.

## StampEdit / EditPlan — les dataclasses du contrat

`src/taskmap/authoring.py:55` (StampEdit) · `:77` (EditPlan) · frozen.
`StampEdit` : mutation déclarative — champs `None`/vides = slot **intact** ; `epic`/`blueprint` set (écrase),
`*_add`/`*_remove` union/retrait sur listes, `clear` vide des slots. **Aucun champ `axis`** (structurellement
non écrivable). `EditPlan` : `{new_text, changed, diff}` — résultat pur de `plan_edit`.

## selftest() — la preuve in-module (I4)

`src/taskmap/authoring.py:236` · `python -m taskmap.authoring`.
Vérifie pose/mute/idempotence/préservation-corps/rang canonique/refus (posture invalide, `axis` non écrivable,
frontmatter absent) sur un frontmatter in-memory — aucun I/O.

## Zones non détaillées (signalées)

- `_desired_line` (`:126`, état-cible d'un slot), `_place_slot` (`:168`, remplace/insère au rang), `_merge_list`
  (`:159`, union ordonnée dédupliquée), `_key_spans` (`:192`, spans des clés top-level), `_SKIP`/`_RANK` :
  mécanique d'édition ligne-à-ligne, lisible au fil du code. Le contrat de mutation complet : la décision vault
  citée en tête.
