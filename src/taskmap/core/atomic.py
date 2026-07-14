"""atomic — écriture fichier atomique (tempfile même-répertoire + os.replace).

Port stdlib-pur de l'idiome maison du vault (`.claude/scripts/lib/core/atomic.py`) : on écrit dans un
tempfile du **même répertoire** que la cible (`os.replace` reste atomique — un rename cross-device lèverait
`OSError`), puis on renomme. Sur exception en cours d'écriture, la cible reste **intacte** et le tempfile est
nettoyé : jamais de demi-écriture, jamais de lecture d'un fichier tronqué.

Caveat (comme la source) : l'atomicité ne protège PAS un *read-modify-write* concurrent (lost update).
L'usage de `authoring` est **mono-user local** (écrivain unique) → pas de lock. Le jour où plusieurs
écrivains muteraient la même task en parallèle, sérialiser la section critique EN PLUS.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path


def write_text(path: Path | str, text: str, *, encoding: str = "utf-8") -> Path:
    """Écrit `text` dans `path` de façon atomique (tempfile même-répertoire + `os.replace`).

    Crée le dossier parent au besoin. Retourne le chemin écrit. Sur exception en cours d'écriture, la cible
    existante est préservée et le tempfile retiré (pas de fichier partiel laissé derrière).
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=f".{p.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(text)
        os.replace(tmp, p)  # rename atomique (même filesystem)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return p
