---
name: work-loop
description: Boucle de travail sûre et lightweight sur CE repo — sans centre de contrôle. Toujours sur une worktree feature depuis dev, gate vert, main jamais cassé. Version manuelle de ce que le forgemaster automatise.
inputs: [sujet de la feature]
outputs: [feature mergée dans dev, gate vert, worktree nettoyée]
related_catalogs: []
---

# work-loop — travailler ce repo en autonomie légère (sans forgemaster)

## Quand l'utiliser

À **chaque** évolution du repo, que tu sois une IA (`claude`) ou un humain, sur un simple clone. C'est la
version **manuelle et lightweight** de la boucle que le **forgemaster automatise** (dispatch → worktree → gate →
merge). Aucun daemon, aucune DB, aucun réseau requis : juste `git` + le skill `quality-gate`. Le repo est
**auto-travaillable seul** ; le forgemaster est un orchestrateur *optionnel* par-dessus, aux **mêmes invariants**.

## Invariants (non négociables)

1. **`main` est protégé** : ce n'est **jamais** la surface de travail. Il n'avance **que** par fast-forward
   depuis un `dev` vert. Jamais l'inverse, jamais un commit direct.
2. **Tout travail vit sur `feature/<sujet>`**, créée **depuis `dev`**, dans une **worktree isolée**.
3. **Aucun merge sans gate vert** (`quality-gate`). Un acte **irréversible** (merge, destroy, push distant)
   exige un **feu vert humain explicite** — fail-closed (une IA ne merge/ne pousse jamais seule).

## Boucle

```bash
REPO=$(git rev-parse --show-toplevel)        # racine du repo courant
FEAT=<sujet-kebab-case>                        # ex. port-graph-engine

# 1. Partir de dev à jour, dans une worktree feature isolée
git -C "$REPO" fetch --prune 2>/dev/null || true
git -C "$REPO" worktree add "../$(basename "$REPO")-$FEAT" -b "feature/$FEAT" dev
cd "../$(basename "$REPO")-$FEAT"

# 2. Travailler ici (IA ou humain). Anti-archéologie : interroger la doc/le code avant de grep à l'aveugle.

# 3. Gate — skill `quality-gate` (ruff + mypy + pytest).
#    Rouge → corriger la CAUSE, jamais contourner ni déplacer un seuil.

# 4. E2E si pertinent : CLI → smoke réel (`taskmap --help` répond, la commande produit le RÉSULTAT attendu).
#    L'IA propose ; un humain valide tout effet irréversible.
```

Puis, **après feu vert** :

```bash
# 5. Lander dans dev (ff-only : refuse si dev a divergé → rebaser d'abord)
git -C "$REPO" switch dev && git -C "$REPO" merge --ff-only "feature/$FEAT"

# 6. Promouvoir main — DÉLIBÉRÉ, seulement quand dev est vert (jamais l'inverse)
git -C "$REPO" switch main && git -C "$REPO" merge --ff-only dev

# 7. Nettoyer (push distant seulement si un remote existe — local-first à ce stade)
git -C "$REPO" worktree remove "../$(basename "$REPO")-$FEAT"
git -C "$REPO" branch -d "feature/$FEAT"
```

## Sortie

Une feature **complète**, gate vert, mergée dans `dev` en ff-only, `main` promu depuis un `dev` vert, la
worktree et la branche nettoyées. À aucun moment `main` n'a été la surface de travail ni cassé.

## Rapport au forgemaster

Le forgemaster fait **exactement** ceci — worktree feature comme mutex, gate, merge, GO humain fail-closed — mais
**automatisé**, **multi-projet**, avec DB + web. Ce skill est le même contrat en **manuel** : suffisant pour
faire vivre un clone seul.
