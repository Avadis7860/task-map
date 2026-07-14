"""test_config — chargement du vocab + emplacement des tasks depuis `.taskmap.toml` (P2).

Le socle `.taskmap.toml`/périmètre de P0 est couvert par `test_skeleton.py` ; ici on cible l'externalisation
du vocab métier (priorités/services/catégories) et du `tasks_subdir`, avec les défauts permissifs.
"""
from __future__ import annotations

from pathlib import Path

from taskmap.config import (
    DEFAULT_CATEGORIES,
    DEFAULT_PRIORITIES,
    DEFAULT_SERVICES,
    DEFAULT_TASKS_SUBDIR,
    Config,
)


def test_defaults_are_permissive_without_file(tmp_path: Path):
    """Sans `.taskmap.toml` : services/catégories VIDES (permissif), priorités = défaut ordonné P0…P3."""
    cfg = Config.load(tmp_path)
    assert cfg.services == DEFAULT_SERVICES == frozenset()
    assert cfg.categories == DEFAULT_CATEGORIES == frozenset()
    assert cfg.priorities == DEFAULT_PRIORITIES == ("P0", "P1", "P2", "P3")
    assert cfg.tasks_subdir == DEFAULT_TASKS_SUBDIR == (".claude", "tasks")


def test_prio_property_orders_priorities():
    """La propriété `prio` mappe chaque priorité sur son rang (source unique du ranking)."""
    cfg = Config(priorities=("A", "B", "C"))
    assert cfg.prio == {"A": 0, "B": 1, "C": 2}


def test_reads_vocab_table(tmp_path: Path):
    """`[vocab]` → priorités (tuple ordonné), services/catégories (frozenset)."""
    (tmp_path / ".taskmap.toml").write_text(
        '[vocab]\n'
        'priorities = ["high", "low"]\n'
        'services = ["web", "api"]\n'
        'categories = ["feat", "fix"]\n',
        encoding="utf-8",
    )
    cfg = Config.load(tmp_path)
    assert cfg.priorities == ("high", "low")
    assert cfg.services == frozenset({"web", "api"})
    assert cfg.categories == frozenset({"feat", "fix"})
    assert cfg.prio == {"high": 0, "low": 1}


def test_reads_tasks_subdir(tmp_path: Path):
    """`[tasks].subdir` (liste de segments) → tuple ; override de la disposition par défaut."""
    (tmp_path / ".taskmap.toml").write_text(
        '[tasks]\nsubdir = ["work", "items"]\n', encoding="utf-8",
    )
    cfg = Config.load(tmp_path)
    assert cfg.tasks_subdir == ("work", "items")


def test_partial_config_keeps_defaults(tmp_path: Path):
    """Une config partielle (juste `[vocab].services`) garde les défauts sur les autres champs."""
    (tmp_path / ".taskmap.toml").write_text(
        '[vocab]\nservices = ["only"]\n', encoding="utf-8",
    )
    cfg = Config.load(tmp_path)
    assert cfg.services == frozenset({"only"})
    assert cfg.priorities == DEFAULT_PRIORITIES          # non déclaré → défaut
    assert cfg.tasks_subdir == DEFAULT_TASKS_SUBDIR        # non déclaré → défaut
