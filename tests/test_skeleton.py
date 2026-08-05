"""Fumée du squelette : le package s'importe, le CLI se câble, le socle core marche (avant le port du moteur).

Ces tests garantissent que la STRUCTURE tient (imports, parser figé, root-resolver, config) pendant qu'on
porte les couches une par une (moteur en P1, CLI en P5). Complétés par les vrais tests de correction ensuite.
"""
from __future__ import annotations

from pathlib import Path

import pytest

VERBS = ["context", "link", "unlink", "rollup", "doctor"]


def test_package_imports():
    import taskmap

    assert taskmap.__version__ == "0.1.0"
    assert taskmap.SCHEMA_VERSION == "0.1.0"


def test_public_api_is_reachable_from_the_package_root():
    """L'API que le README annonce s'importe depuis `taskmap`, sans passer par un module interne.

    Deux surfaces sont nommées au lecteur : le **classement de disponibilité** (`classify` + le moteur de
    graphe) et le **verdict blueprint** (la promesse « jamais une réponse inventée »). Un consommateur qui
    doit descendre dans `taskmap.core.*` ou attraper un `_nom` pour les atteindre lit une promesse que le
    paquet ne tient pas — c'est ce qui était arrivé aux trois symboles ci-dessous.
    """
    from taskmap import blueprint_verdict, classify, eff_prio, rank_ready

    for fn in (blueprint_verdict, classify, eff_prio, rank_ready):
        assert callable(fn)


def test_public_surface_declares_no_private_name():
    """Rien de privé ne se faufile dans `__all__` — la garde qui empêche la régression de se réinstaller."""
    import taskmap

    assert not [n for n in taskmap.__all__ if n.startswith("_") and n != "__version__"]
    for name in taskmap.__all__:
        assert hasattr(taskmap, name), f"`{name}` déclaré public mais absent du package"


def test_cli_parser_builds_and_lists_subcommands():
    from taskmap.cli import build_parser

    parser = build_parser()
    subactions = [a for a in parser._actions if a.dest == "cmd"]
    assert subactions, "aucune sous-commande câblée"
    choices = set(subactions[0].choices)
    assert set(VERBS) <= choices


def test_version_and_schema_version_exit_clean(capsys: pytest.CaptureFixture[str]):
    """`--version` et `--schema-version` impriment puis sortent (SystemExit 0), sans index ni logique."""
    from taskmap.cli import main

    for flag, expected in (("--version", "0.1.0"), ("--schema-version", "0.1.0")):
        with pytest.raises(SystemExit) as exc:
            main([flag])
        assert exc.value.code == 0
        assert expected in capsys.readouterr().out


def test_roots_resolves_by_marker(tmp_path: Path):
    """roots : un dossier avec .git (ou .taskmap.toml) est reconnu comme racine ; sinon fallback sur start."""
    from taskmap.core import roots

    (tmp_path / ".git").mkdir()
    assert roots.project_root(start=tmp_path) == tmp_path.resolve()

    (tmp_path / "sub").mkdir()
    # remontée depuis un sous-dossier jusqu'au repère
    assert roots.project_root(start=tmp_path / "sub") == tmp_path.resolve()

    # `--root` explicite l'emporte
    assert roots.project_root(explicit=tmp_path) == tmp_path.resolve()


def test_roots_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from taskmap.core import roots

    monkeypatch.setenv("TASKMAP_ROOT", str(tmp_path))
    assert roots.project_root() == tmp_path.resolve()


def test_config_defaults_without_file(tmp_path: Path):
    """Config.load rend les défauts permissifs quand `.taskmap.toml` est absent."""
    from taskmap.config import Config

    cfg = Config.load(tmp_path)
    assert cfg.include == []
    assert cfg.exclude == []


def test_config_reads_perimeter(tmp_path: Path):
    from taskmap.config import Config

    (tmp_path / ".taskmap.toml").write_text(
        '[perimeter]\ninclude = ["a", "b"]\nexclude = ["c"]\n', encoding="utf-8"
    )
    cfg = Config.load(tmp_path)
    assert cfg.include == ["a", "b"]
    assert cfg.exclude == ["c"]


@pytest.mark.parametrize("verb", VERBS)
def test_handlers_are_live(verb: str, tmp_path):
    """Depuis P5 chaque verbe est CÂBLÉ : sur une racine vide il s'exécute (rc 0, enveloppe JSON), il ne lève
    plus `NotImplementedError`. La correction fine vit dans test_context.py / test_cli.py."""
    from taskmap.cli import main

    (tmp_path / ".taskmap.toml").write_text('[tasks]\nsubdir = [".claude", "tasks"]\n', encoding="utf-8")
    argv = {
        "context": ["context", "foo"],
        "link": ["link", "foo", "epic=x"],
        "unlink": ["unlink", "foo", "epic"],
        "rollup": ["rollup", "axis", "un-axe"],
        "doctor": ["doctor"],
    }[verb] + ["--root", str(tmp_path)]
    assert main(argv) == 0  # ne lève pas NotImplementedError
