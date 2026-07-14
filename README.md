# task-map

> Moteur **déterministe** de liaison des tasks à leurs ancrages — le protocole **STAMP**. Pour ancrer chaque
> mission dans le tissu du travail (axe north-star · épic servi/débloqué · blueprint appliqué) plutôt que dans
> une liste mtime plate.

**Statut : privé · pré-opérationnel (bootstrap P0 — squelette exécutable, moteur en cours de port).**

6ᵉ outil de la famille `-map` (code-map · docs-map · front-map · bundle-map · mcp-catalogs). Outil **autonome**,
sans service ni réseau : un CLI qui lit les tasks **en live** et rend du JSON stable, consommé par le hook
`session-start` du vault et (à terme) le cockpit.

## Verbes

| Verbe | Rôle | Statut |
|---|---|---|
| `taskmap context <slug>` | les 3 liaisons STAMP d'une task : axe + épic servi/débloqué + blueprint | P5 |
| `taskmap rollup axis <nom>` | agrège tout le travail sous un axe north-star | P5 |
| `taskmap link <slug> <ancre…>` | pose un slot STAMP (écriture atomique, jamais de commit) | P4 |
| `taskmap unlink <slug> <ancre…>` | retire un slot STAMP | P4 |
| `taskmap doctor` | cohérence des liaisons (blueprint mort, épic inexistant, axe non résolu) | P5 |
| `taskmap --schema-version` | version du contrat de sortie (négociation consommateur) | P0 ✓ |

À P0 la **structure** de la CLI est figée et le squelette s'exécute (`--help`/`--version`/`--schema-version`) ;
les verbes sont des stubs honnêtes (`NotImplementedError` avec pointeur de phase) tant que le moteur n'est pas
porté.

## Principes

- **Cœur stdlib-pur** : aucune dépendance obligatoire → installable partout, offline, sans compilation. La
  résolution des refs blueprint via le MCP `mcp-catalogs` (P5) est une **intégration optionnelle à dégradation
  honnête**, jamais une dépendance dure.
- **Enveloppe de sortie figée** (`{ok, schema_version}`, rc 0 pour lecture) : contrat inter-repos — cf.
  [`docs/schema-contract.md`](./docs/schema-contract.md).
- **Lecture live, pas d'index dérivé** : le corpus tasks est minuscule (comme bundle_map lit ses manifestes) →
  pas de `build`, pas de cache à rafraîchir.
- **Générique par configuration** : ce qui varie d'un vault à l'autre se déclare dans un
  [`.taskmap.toml`](./.taskmap.toml) (défauts génériques si absent). Aucun chemin en dur.
- **Jamais de git** : l'écriture (P4) pose le fichier ; un humain / le cockpit commit.

## Installation

```bash
pip install -e .            # cœur stdlib-pur, zéro dépendance
pip install -e '.[dev]'     # + pytest / ruff / mypy
```

Résolution de racine générique : `--root <path>`, sinon `$TASKMAP_ROOT`, sinon remontée depuis le cwd jusqu'au
repère (`.taskmap.toml` ou `.git/`).

## Architecture

Voir [`docs/architecture.md`](./docs/architecture.md) (protocole STAMP + couches) et
[`docs/schema-contract.md`](./docs/schema-contract.md) (enveloppe de sortie figée).

## Licence

Propriétaire — voir [`LICENSE`](./LICENSE). Tous droits réservés.
