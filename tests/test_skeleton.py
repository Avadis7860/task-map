"""Fumée du squelette : le package s'importe, le CLI se câble, le socle core marche (avant le port du moteur).

Ces tests garantissent que la STRUCTURE tient (imports, parser figé, root-resolver, config) pendant qu'on
porte les couches une par une (moteur en P1, CLI en P5). Complétés par les vrais tests de correction ensuite.
"""
from __future__ import annotations

from pathlib import Path

import pytest

STUB_VERBS = ["context", "link", "unlink", "rollup", "doctor"]


def test_package_imports():
    import taskmap

    assert taskmap.__version__ == "0.1.0"
    assert taskmap.SCHEMA_VERSION == "0.1.0"


def test_cli_parser_builds_and_lists_subcommands():
    from taskmap.cli import build_parser

    parser = build_parser()
    subactions = [a for a in parser._actions if a.dest == "cmd"]
    assert subactions, "aucune sous-commande câblée"
    choices = set(subactions[0].choices)
    assert set(STUB_VERBS) <= choices


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


@pytest.mark.parametrize("verb", STUB_VERBS)
def test_stub_handlers_are_honest(verb: str):
    """Chaque verbe est un STUB honnête à P0 : il lève NotImplementedError (avec pointeur de phase), il ne
    renvoie jamais un faux résultat vide. La logique est portée en P4/P5."""
    from taskmap.cli import build_parser

    parser = build_parser()
    argv = {
        "context": ["context", "foo"],
        "link": ["link", "foo", "axis=x"],
        "unlink": ["unlink", "foo", "axis=x"],
        "rollup": ["rollup", "axis", "env-dev-workers-ia"],
        "doctor": ["doctor"],
    }[verb]
    ns = parser.parse_args(argv)
    with pytest.raises(NotImplementedError):
        ns.func(ns)
