# CLAUDE.md — task-map (moteur déterministe de liaison des tasks · protocole STAMP)

> Lu au début de **chaque** session dans ce repo. Persona `tool-builder`.
> Ce fichier = **règles + index + outils**, PAS la spec. Le détail (couches, contrat de schéma, modèle STAMP)
> vit dans `docs/` — **interroge-le** (`docsmap where` si branché), ne le recopie pas ici.

## Règles (non négociables)

- **Boucle de travail** : tout changement passe par le skill **`work-loop`** — worktree `feature/<sujet>`
  créée **depuis `dev`**, gate vert, puis `dev` en ff-only. **`main` ne se travaille jamais** : il n'avance
  que promu depuis un `dev` vert. Jamais de commit direct sur `main`/`dev`.
- **Gate avant merge** : `ruff` + `mypy` + `pytest` **verts** (skill `quality-gate`). Un acte irréversible
  (merge/destroy/push distant) = **feu vert humain, fail-closed**.
- **Anti-boucle** : pas de signature d'API inventée « de mémoire » — lis la stdlib / le code / la doc.
- **Anti-archéologie** : interroge les index au lieu de fouiller à l'aveugle (`docsmap where` pour la prose de
  `docs/` si branché ; ne la lis jamais en bloc pour t'orienter).
- **Invariants du cœur** : cœur **stdlib-pur** (aucune dép obligatoire ; toute intégration — ex. résolution MCP
  du ref blueprint — est **optionnelle à dégradation honnête**, jamais une dép dure) · **enveloppe de sortie =
  contrat figé** inter-repos (`{ok, schema_version}`, rc 0 pour lecture ; changer un champ figé → bump +
  changelog) · **lecture live** (pas d'index dérivé — corpus tasks minuscule, comme bundle_map) · **jamais de
  cap silencieux** · **rien de spécifique-projet en dur** (`.taskmap.toml`) · **jamais de git** (l'écriture pose
  le fichier, un humain/le cockpit commit).
- Fixtures minuscules, **noms fictifs** (jamais un vrai basename de projet).

## Index (interroge, ne lis pas en bloc)

- `docs/architecture.md` — intention, protocole STAMP, les couches, **frontières délibérées** (pas d'index
  bâti, pas de recopie du corpus capital, jamais de git), CLI unifié.
- `docs/schema-contract.md` — enveloppe de sortie `{ok, schema_version}`, négociation de version, forme de
  `context` (figée en P5).
- `PORTING.md` — journal d'extraction depuis `vault_tasks.py` (état vivant).

## Outils à disposition (embarqués dans ce repo)

- **Skills** (`.claude/skills/`) : `work-loop` (boucle de travail sûre, lightweight, sans cockpit) ·
  `quality-gate` (ruff + mypy + pytest).
- **Hook** (`.claude/hooks/post-edit-check.py`) : `py_compile` + `ruff` sur le `.py` touché à chaque édition.
- **Persona** (`.claude/output-styles/tool-builder.md`) : posture outilleur déterministe.

## Rapport au cockpit (auto-travaillable seul)

Ce repo est **auto-travaillable en autonomie légère** : un clone suffit pour qu'un worker — IA `claude` **ou**
humain — le fasse évoluer en sûreté via `work-loop`, **sans aucun centre de contrôle**. Le **cockpit** automatise
exactement cette boucle par-dessus ; il est **optionnel**, jamais requis. Mêmes invariants des deux côtés :
worktree `feature` depuis `dev`, gate vert avant merge, `main` protégé, **GO humain sur tout acte irréversible**.
