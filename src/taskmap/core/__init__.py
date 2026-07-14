"""core — socle stdlib partagé, data-shape-agnostique (zéro import taskmap, consommable cross-repo).

- `roots` : résolution de racine ; `atomic` : écriture atomique.
- `graph` : cœur de séquencement du DAG — `detect_cycles`, `eff_prio` (priorité effective transitive),
  `rank_key`/`rank_ready`/`resolve_next` (rang canonique). Foyer public du moteur porté : le vault le nourrit
  via `classify`, un tiers via ses propres rows projetés. Cf. `graph.py` pour le contrat de record générique.
"""
