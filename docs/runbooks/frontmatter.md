# frontmatter — runbook (parseur YAML stdlib-pur, remplace PyYAML)

`src/taskmap/frontmatter.py` — parsing du frontmatter YAML des tasks **sans dépendance** (tient l'invariant
`dependencies=[]` de la famille `-map`). Ce n'est **pas** un parseur YAML général : il couvre le sous-ensemble
EXACT du corpus (block-maps, block-seqs `- x`/`- clé: v`, flow-seqs `[a, b]`, scalaires typés, quotes,
commentaires inline, blocs `|`/`>`). Ancres et multi-documents sont hors scope. **Parité** : les types résolus
miment PyYAML 1.1 `safe_load` (null/bool/int/date) pour qu'un port 1:1 du moteur produise un index identique —
une date ISO non quotée devient un `datetime.date` (comme PyYAML), prouvé par `tools/parity_check.py`.

## split_frontmatter() — (frontmatter dict, corps)

`src/taskmap/frontmatter.py:32` · **home unique** du parsing frontmatter · appelé par `graph.load_tasks`,
`authoring.plan_edit`, `context.extract_stamp`.
Découpe le bloc `---\n…\n---` en tête (tolère l'absence → `({}, text)`), parse la région entre fences via le
parseur récursif interne. **Invariant** : un frontmatter non-map résout en `{}` (jamais un crash). C'est la
frontière que tout le moteur partage — un seul point de vérité pour « comment lire le frontmatter d'une task ».

## load() — un document YAML complet (sans fences)

`src/taskmap/frontmatter.py:43` · appelé par `northstar.load_manifest`.
Parse un doc **autonome** (un manifeste, pas un frontmatter) avec le même sous-ensemble et le même parseur
récursif. Doc vide → `{}`. Sert le manifeste north-star sans ajouter de dépendance — même socle, deux points
d'entrée.

## Zones non détaillées (signalées, non faux-complétées)

- Tout l'**arbre de descente récursive** : `_parse` (`:176`), `_parse_block`/`_parse_map`/`_parse_seq`
  (`:184`/`:191`/`:223`), `_parse_flow_seq`/`_parse_flow_map`/`_parse_scalar` (`:291`/`:299`/`:312`),
  `_resolve` (résolution de type PyYAML-1.1, `:318`), `_tokenize`/`_strip_comment` (`:79`/`:54`),
  `_collapse_block_scalars`/`_fold_lines`/`_dq_escape` (préservation des blocs `|`/`>`), `_unquote_*`.
  Mécanique de parsing pure — indispensable au fonctionnement, se lit au fil du code. La règle de parité
  PyYAML 1.1 et le sous-ensemble couvert : docstring du module + `tools/parity_check.py`.
