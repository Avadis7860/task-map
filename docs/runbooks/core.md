# core — runbook (socle générique stdlib-pur, consommable cross-repo)

`src/taskmap/core/` — primitives sans dépendance, **data-shape-agnostiques**. `core/graph` **implémente** le
**moteur de séquencement** consommable cross-repo : le vault le nourrit avec ses records STAMP, un tiers (le
forgemaster) avec ses propres rows projetés (SQLite) → **une seule copie vivante du moteur, dé-fork par import
runtime**. Le cœur ne connaît ni markdown, ni slots STAMP, ni vocab métier — juste une forme de record
minimale (`id`/`depends_on`/`priority`/`created`/`optional`), lue **défensivement**.

> **Ce dossier n'est pas une adresse publique.** `detect_cycles`/`eff_prio`/`rank_ready` se consomment par
> **`taskmap.graph`**, qui les ré-exporte. `core/` est le socle interne — même sens que dans les autres repos
> `-map`, où il est explicitement une copie vendorisée. Un consommateur qui écrit `taskmap.core.graph`
> s'accroche à un emplacement, pas à un contrat.

## core.graph.eff_prio() — priorité effective transitive

`src/taskmap/core/graph.py:55` · appelé par `rank_ready` · **graduée du fork forgemaster** (distillation-vers-le-centre).
`eff(t) = min(rang propre, min sur dépendants transitifs)` : une task de faible priorité qui **débloque** une
task plus prioritaire **remonte**. `prio` = vocab ORDONNÉ (P0=0…) ; hors-vocab ⇒ `len(prio)` (fail-soft,
dernier). Récursion sur les arêtes **inverses** (`dependents`), **mémoïsée**, garde de pile anti-cycle. C'est le
gain de `eff_prio` sur l'ancien rang plat, devenu le rang canonique des DEUX consommateurs.

## core.graph.rank_key() / rank_ready() / resolve_next() — le rang canonique

`src/taskmap/core/graph.py:83` (rank_key) · `:91` (rank_ready) · `:101` (resolve_next).
`rank_key` : ordre total `(eff_prio ↑, optionnel après, création ↑, id)` — zéro ex-æquo ; pour un row forgemaster
(`optional`=0, `id`≡`slug`) se réduit à `(eff, created, id)` (ordre du fork **préservé**). `rank_ready` : les
tasks **READY** dans `scope_pred`, triées par ce rang (tête = la NEXT dispatchable). `resolve_next` : la tête,
ou `None`. Source **unique** du ranking, partagée vault ↔ forgemaster.

## core.graph.detect_cycles() — membres d'un cycle de dépendances

`src/taskmap/core/graph.py:30` · **déplacé ici** (re-exporté par `taskmap.graph` pour la back-compat) · appelé
par `classify`.
DFS colorée (white/grey/black) ; arêtes dangling ignorées ; graphes petits. Rend le set des ids membres d'un
cycle → `classify` les marque CYCLE, `doctor` les remonte en `problems`.

## core.atomic.write_text() — écriture fichier atomique

`src/taskmap/core/atomic.py:19` · appelé par `authoring.apply_edit`.
Tempfile du **même répertoire** que la cible + `os.replace` (rename atomique intra-filesystem ; cross-device
lèverait `OSError`). Crée le parent au besoin. **Invariant** : sur exception en cours d'écriture, la cible
reste **intacte** et le tempfile est nettoyé — jamais de demi-écriture ni de lecture tronquée. Caveat : ne
protège PAS un read-modify-write concurrent (usage mono-user local, pas de lock).

## core.roots.project_root() / rel() — racine générique + chemin relatif

`src/taskmap/core/roots.py:22` (project_root) · `:36` (rel) · appelé par `cli._resolve`.
`project_root` résout dans l'ordre : `--root` explicite → `$TASKMAP_ROOT` → remontée vers le 1er répertoire
portant `.taskmap.toml` ou `.git/` → cwd. **Jamais** de `parents[N]` fixe (invariant I5, généralisé du vault :
plus aucune notion de vault). `rel` = chemin POSIX relatif à la racine (clé d'identité stable).

## Zones non détaillées

- La forme de record générique attendue et son contrat défensif : docstring de `core/graph.py`. La sentinelle
  de mémoïsation et les gardes de pile : lisibles inline.
