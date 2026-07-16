# context — runbook (les verbes de LECTURE de STAMP : context / rollup / doctor)

`src/taskmap/context.py` — read-only, live. **Re-parse les slots STAMP directement du frontmatter**
(`epic`/`serves`/`unblocks`/`blueprint`/`template`) : le moteur de graphe ne garde que `depends_on` dans son
record. `axis` n'est **jamais lu ni stocké** — dérivé via `northstar.axis_for_epic` (I1, pas de 2ᵉ SoT). La
résolution du blueprint ref est **déléguée** au consommateur MCP : task-map reste offline/stdlib-pur/sans
secret (verdict `resolved:false` + raison honnête par défaut ; jamais inventé). Contrat : décision vault
`2026-07-14--taskmap-mcp-degradation-contract.md`. Séparation pur/impur (I4).

## build_context() — les 3 liaisons STAMP d'une task

`src/taskmap/context.py:131` · appelé par `cli._cmd_context`.
Rend axe **dérivé** · épic servi + `serves`/`unblocks` · blueprint (ref + verdict). Charge l'index, extrait
les slots du frontmatter réel (`extract_stamp`), dérive l'axe si un manifeste est chargé et l'épic présent,
résout le blueprint (`_blueprint_verdict`). Task absente → `{ok:false, reason}` (échec logique, rc 0 côté CLI).

## rollup_axis() — agrège les tasks sous un axe dérivé

`src/taskmap/context.py:148` · appelé par `cli._cmd_rollup`.
Agrège les tasks dont l'axe **dérivé** (épic → axe primaire) == `name`. Pas de manifeste / axe inconnu →
`{ok:false, reason}` honnête. Membres triés par slug (déterministe). L'axe n'est jamais stocké : re-dérivé par
task via `extract_stamp` + `northstar.axis_for_epic`.

## doctor() — cohérence des liaisons (problems durs vs warnings advisory)

`src/taskmap/context.py:170` · appelé par `cli._cmd_doctor` et le proactive-tasks du vault.
Deux niveaux **distincts**. `problems` (DURS → bascule `ok:false`) : graphe corrompu (dep dangling / cycle,
via `classify`), manifeste north-star incohérent (`northstar.validate`), intégrité STAMP (épic hors carte ;
blueprint mort **si** un resolver est fourni). `warnings` (advisory, **ne bascule PAS** `ok`) : hygiène tasks
déjà surfacée (réconciliation ROADMAP via `reconcile_epics`, WIP, différés, vocab), dédupliquée des
incohérences dures. Sortie `{checked, problems, warnings, ok}`.

## extract_stamp() — slots STAMP du frontmatter, normalisés (pur)

`src/taskmap/context.py:38` · appelé par `build_context`, `rollup_axis`, `doctor`.
PUR. `epic`→str|None ; `serves`/`unblocks`/`template`→list[str] ; `blueprint`→{id, posture}|None (flow-map ou
scalaire nu). `axis` **jamais extrait** (dérivé). Une task sans slot rend des vides **honnêtes** (pas de
faux-positif).

## _blueprint_verdict() — résolution déléguée, jamais inventée

`src/taskmap/context.py:72` · appelé par `build_context`/`doctor`.
Verdict du slot blueprint. **Défaut** (aucun resolver) : `resolved:false` + raison de délégation honnête. Si un
`resolve` est injecté (seam) : dict véridique → `resolved:true` (+ champs fusionnés) ; `None`/`{}` → liaison
morte signalée ; exception → échec signalé (jamais propagée, ne casse pas le verbe). **Jamais inventé.**

## assemble_context() — le payload figé (pur)

`src/taskmap/context.py:99` · appelé par `build_context`.
Assemble le payload `context` figé : `{slug, axis, epic, serves, unblocks, blueprint, template}`. PUR — l'axe
et le verdict sont injectés tels quels.

## Zones non détaillées

- `_load_manifest` (`:114`, charge le manifeste si configuré + présent, None sinon), `_read` (`:127`),
  `_scalar`/`_strlist`/`_blueprint` (`:54`–`:62`, normalisation) : coquilles/helpers triviaux. Le contrat de
  dégradation MCP : la décision vault citée en tête.
