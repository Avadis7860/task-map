"""config — chargement de `.taskmap.toml` (configuration du vault/repo cible).

Générique et déclaratif à la racine du repo cible ; absent → défauts permissifs. `tomllib` stdlib → zéro
dépendance. C'est ICI que vit le **vocab par défaut** du moteur (P2) : le vocab métier
(`PRIORITIES`/`SERVICES`/`CATEGORIES`) et l'emplacement des buckets tasks, externalisés depuis `graph.py`. Un
repo sans `.taskmap.toml` tourne sur des défauts **permissifs** (services/categories vides ⇒ aucune
validation, aucun warning) ; le vault déclare son vocab FERMÉ dans son propre `.taskmap.toml` et garde ainsi
ses avertissements. La table `[northstar]` (P3) pointe le manifeste north-star (donnée dédiée, `.claude/
northstar.yaml`) ; absent ⇒ pas de rollup d'axe (dégradation honnête).
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_FILENAME = ".taskmap.toml"

# Défauts du moteur. Les priorités portent un ORDRE (requis par le ranking) → défaut non vide, jamais
# permissif. Les services/catégories sont descriptifs → défaut VIDE = permissif (aucun repo tiers réprimandé).
DEFAULT_TASKS_SUBDIR: tuple[str, ...] = (".claude", "tasks")
DEFAULT_PRIORITIES: tuple[str, ...] = ("P0", "P1", "P2", "P3")
DEFAULT_SERVICES: frozenset[str] = frozenset()
DEFAULT_CATEGORIES: frozenset[str] = frozenset()
DEFAULT_PRIO: dict[str, int] = {p: i for i, p in enumerate(DEFAULT_PRIORITIES)}


@dataclass(frozen=True)
class Config:
    """Config résolue d'un repo cible (défauts = comportement générique permissif)."""

    include: list[str] = field(default_factory=list)   # sous-arbres tasks à couvrir ; [] = défaut générique
    exclude: list[str] = field(default_factory=list)   # sous-arbres exclus en plus des défauts
    tasks_subdir: tuple[str, ...] = DEFAULT_TASKS_SUBDIR   # emplacement des 3 buckets sous la racine
    priorities: tuple[str, ...] = DEFAULT_PRIORITIES       # vocab ORDONNÉ des priorités (ranking)
    services: frozenset[str] = DEFAULT_SERVICES            # vocab fermé du service ; vide ⇒ permissif
    categories: frozenset[str] = DEFAULT_CATEGORIES        # vocab fermé de la catégorie ; vide ⇒ permissif
    northstar_manifest: str | None = None   # manifeste north-star (rel. root) ; None ⇒ pas de rollup

    @property
    def prio(self) -> dict[str, int]:
        """Ordre de rang des priorités (P0=0 … ) — source unique consommée par `_rank_key` de classify."""
        return {p: i for i, p in enumerate(self.priorities)}

    @staticmethod
    def load(root: Path) -> Config:
        """Charge `<root>/.taskmap.toml` s'il existe, sinon renvoie les défauts permissifs."""
        p = Path(root) / CONFIG_FILENAME
        if not p.is_file():
            return Config()
        data = tomllib.loads(p.read_text(encoding="utf-8"))
        peri = data.get("perimeter", {})
        tasks = data.get("tasks", {})
        vocab = data.get("vocab", {})
        northstar = data.get("northstar", {})
        subdir = tasks.get("subdir")
        return Config(
            include=list(peri.get("include", [])),
            exclude=list(peri.get("exclude", [])),
            tasks_subdir=tuple(subdir) if subdir else DEFAULT_TASKS_SUBDIR,
            priorities=tuple(vocab.get("priorities", DEFAULT_PRIORITIES)),
            services=frozenset(vocab.get("services", DEFAULT_SERVICES)),
            categories=frozenset(vocab.get("categories", DEFAULT_CATEGORIES)),
            northstar_manifest=northstar.get("manifest") or None,
        )
