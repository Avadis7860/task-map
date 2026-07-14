"""config — chargement de `.taskmap.toml` (configuration du vault/repo cible).

Générique et déclaratif à la racine du repo cible ; absent → défauts permissifs. `tomllib` stdlib → zéro
dépendance. À P0 la config est **minimale** (périmètre seul) : le vocab métier (`PRIORITIES`/`SERVICES`/
`CATEGORIES`) et les chemins de buckets tasks sont externalisés en **P2**, la carte épics→axes north-star en
**P3**. On ne scaffolde pas ces champs par avance (pas de surface spéculative).
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_FILENAME = ".taskmap.toml"


@dataclass(frozen=True)
class Config:
    """Config résolue d'un repo cible (défauts = comportement générique permissif)."""

    include: list[str] = field(default_factory=list)   # sous-arbres tasks à couvrir ; [] = défaut générique
    exclude: list[str] = field(default_factory=list)   # sous-arbres exclus en plus des défauts

    @staticmethod
    def load(root: Path) -> Config:
        """Charge `<root>/.taskmap.toml` s'il existe, sinon renvoie les défauts."""
        p = Path(root) / CONFIG_FILENAME
        if not p.is_file():
            return Config()
        data = tomllib.loads(p.read_text(encoding="utf-8"))
        peri = data.get("perimeter", {})
        return Config(
            include=list(peri.get("include", [])),
            exclude=list(peri.get("exclude", [])),
        )
