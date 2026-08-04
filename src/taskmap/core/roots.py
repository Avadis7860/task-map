"""roots — résolution générique de la racine d'un repo cible.

Port + GÉNÉRALISATION de vault `lib/core/roots.py`. L'original cherchait un vault (`CLAUDE.md` + `.claude/`),
donc spécifique. Ici, aucune notion de vault — on résout la racine de tout repo cible, dans l'ordre :

    1. `--root` explicite (le plus spécifique) ;
    2. `$TASKMAP_ROOT` (posé par un déploiement / le forgemaster) ;
    3. remontée depuis `start` (ou le cwd) jusqu'au premier répertoire-repère contenant
       `.taskmap.toml` OU `.git/` ;
    4. sinon, `start` (ou cwd) tel quel.

Ne code JAMAIS un `parents[N]` fixe (invariant I5 : root-resolver unique par marqueur, importé par le pkg).
"""
from __future__ import annotations

import os
from pathlib import Path

_MARKERS = (".taskmap.toml", ".git")


def project_root(explicit: Path | str | None = None, start: Path | None = None) -> Path:
    """Racine du repo cible (voir ordre de priorité dans le docstring du module)."""
    if explicit:
        return Path(explicit).expanduser().resolve()
    env = os.environ.get("TASKMAP_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    here = (start or Path.cwd()).resolve()
    for d in (here, *here.parents):
        if any((d / m).exists() for m in _MARKERS):
            return d
    return here


def rel(root: Path, p: Path) -> str:
    """Chemin de `p` relatif à `root` en POSIX, ou `p` tel quel si hors de `root`."""
    try:
        return Path(p).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return str(p)
