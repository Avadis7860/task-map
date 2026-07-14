"""cli — porte d'entrée unifiée `taskmap` (moteur STAMP : liaison des tasks à leurs ancrages).

Une commande, des sous-commandes, un `--root`, un `.taskmap.toml`. Le câblage argparse est complet ici (la
STRUCTURE de la CLI est **figée** dès P0) ; chaque handler délègue à sa couche. À P0 les couches ne sont pas
encore portées : les handlers lèvent `NotImplementedError` avec un pointeur de phase — le squelette s'exécute
et `--help`/`--version`/`--schema-version` fonctionnent.

Contrairement à code-map, taskmap **n'a pas d'index dérivé bâti** : le corpus tasks est minuscule et lu en
**live** (comme bundle_map lit ses manifestes). Donc pas de sous-commande `build`, pas de `--out`, pas de
garde index-absent. La lecture d'une task est directe.

Sous-commandes (surface figée, portée en P5 sauf mention) :
  context <slug>              les 3 liaisons STAMP : axe north-star + épic servi/débloqué + blueprint
  link <slug> <ancre…>        pose un slot STAMP sur une task (écriture — porté en P4, gated)
  unlink <slug> <ancre…>      retire un slot STAMP d'une task (écriture — porté en P4, gated)
  rollup <dimension> <nom>    agrège le travail sous un axe (`rollup axis <nom>`)
  doctor                      cohérence des liaisons (blueprint mort, épic inexistant, axe non résolu)
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from taskmap import SCHEMA_VERSION, __version__, context
from taskmap.authoring import AuthoringError, StampEdit, apply_edit, plan_edit
from taskmap.config import Config
from taskmap.core import roots
from taskmap.graph import load_tasks


class _SchemaVersionAction(argparse.Action):
    """`--schema-version` : imprime la version du CONTRAT (enveloppe + modèle STAMP) et sort — comme
    `--version` mais pour la négociation inter-repos. Un consommateur (hook session-start, cockpit)
    l'interroge pour câbler sa clé de cache / vérifier la compat, avant tout appel de lecture."""

    def __init__(self, option_strings, dest, **kw):  # noqa: ANN001
        super().__init__(option_strings, dest, nargs=0, **kw)

    def __call__(self, parser, namespace, values, option_string=None):  # noqa: ANN001
        print(SCHEMA_VERSION)
        parser.exit()


def _resolve(root_opt: str | None) -> tuple[Path, Config]:
    """Résout (racine, config) pour toute sous-commande. Pas d'`index_dir`/`--out` : lecture live du corpus
    tasks sous la racine (pas d'index dérivé — cf. docstring du module)."""
    root = roots.project_root(root_opt)
    return root, Config.load(root)


def _emit(data: dict) -> int:
    """Émet le payload JSON sous **enveloppe uniforme** (contrat inter-repos) : tout verbe de lecture porte
    `ok` (bool) et `schema_version`. `ok` défaut `True` ; un payload qui pose déjà `ok:false` (échec logique :
    task introuvable, liaison morte) l'emporte. **Code de retour** : les verbes JSON sortent **rc 0** — le
    succès logique se lit dans le corps (`ok`), pas dans rc (cf. docs/schema-contract.md)."""
    payload = {"ok": True, **data, "schema_version": SCHEMA_VERSION}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


# --- Grammaire d'ancre (link/unlink) -----------------------------------------------------------------------

_LIST_KEYS: tuple[str, ...] = ("serves", "unblocks", "template")
_ANCHOR_KEYS: tuple[str, ...] = ("epic", "blueprint", *_LIST_KEYS)


def _build_stamp_edit(tokens: list[str], *, removing: bool) -> StampEdit:
    """Parse les ancres `clé=valeur[:posture]` en `StampEdit`. PUR (échoue en `AuthoringError`).

    `epic=<id>` · `blueprint=<id>:<posture>` · `serves=a,b` · `unblocks=a` · `template=<bp>/<n>.md`.
    unlink : `serves=a` retire `a` ; une ancre NUE (`epic`, `blueprint`, `serves`) vide le slot (`clear`).
    `axis=…` est refusé (slot dérivé, non écrivable).
    """
    kwargs: dict = {}
    clear: set[str] = set()
    for tok in tokens:
        key, sep, raw = tok.partition("=")
        key = key.strip()
        val: str | None = raw.strip() if sep else None
        if key == "axis":
            raise AuthoringError("axis est dérivé (épic→axe), non écrivable — retire l'ancre 'axis='")
        if key not in _ANCHOR_KEYS:
            raise AuthoringError(f"ancre inconnue : {key!r} (∈ {', '.join(_ANCHOR_KEYS)})")
        if removing and not val:
            clear.add(key)
            continue
        if not val:
            raise AuthoringError(f"ancre sans valeur : '{key}=' attend une valeur")
        if key == "epic":
            kwargs["epic"] = val
        elif key == "blueprint":
            bid, bsep, posture = val.partition(":")
            if not bsep:
                raise AuthoringError("'blueprint=' attend <id>:<posture> "
                                     "(posture ∈ applies/tests/updates-candidate)")
            kwargs["blueprint"] = (bid.strip(), posture.strip())
        else:  # slot-liste
            items = tuple(x.strip() for x in val.split(",") if x.strip())
            kwargs[f"{key}_{'remove' if removing else 'add'}"] = items
    if clear:
        kwargs["clear"] = frozenset(clear)
    return StampEdit(**kwargs)


# --- Handlers ----------------------------------------------------------------------------------------------

def _cmd_context(a: argparse.Namespace) -> int:
    root, cfg = _resolve(a.root)
    return _emit(context.build_context(root, a.slug, cfg))


def _cmd_rollup(a: argparse.Namespace) -> int:
    root, cfg = _resolve(a.root)
    return _emit(context.rollup_axis(root, a.name, cfg))


def _cmd_doctor(a: argparse.Namespace) -> int:
    root, cfg = _resolve(a.root)
    return _emit(context.doctor(root, cfg))


def _cmd_link(a: argparse.Namespace) -> int:
    return _run_edit(a, removing=False)


def _cmd_unlink(a: argparse.Namespace) -> int:
    return _run_edit(a, removing=True)


def _run_edit(a: argparse.Namespace, *, removing: bool) -> int:
    """Fabrique le `StampEdit` depuis les ancres, calcule le plan (pur), puis `--dry-run` (diff seul) ou écrit
    atomiquement (`apply_edit`, jamais de commit). Task absente / ancre invalide → `ok:false` (rc 0)."""
    root, cfg = _resolve(a.root)
    index, _warns = load_tasks(root, cfg)
    rec = index.get(a.slug)
    if rec is None:
        return _emit({"ok": False, "slug": a.slug, "reason": f"task introuvable : {a.slug}"})
    path = root / rec["path"]
    try:
        edit = _build_stamp_edit(a.anchors, removing=removing)
        plan = plan_edit(path.read_text(encoding="utf-8"), edit)
    except AuthoringError as e:
        return _emit({"ok": False, "slug": a.slug, "reason": str(e)})
    if a.dry_run:
        return _emit({"slug": a.slug, "dry_run": True, "changed": plan.changed, "diff": plan.diff})
    applied = apply_edit(path, plan)
    return _emit({"slug": a.slug, "changed": plan.changed, "applied": applied})


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="taskmap",
                                 description="moteur déterministe de liaison des tasks (STAMP)")
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    ap.add_argument("--schema-version", action=_SchemaVersionAction,
                    help="imprime la version du contrat de schéma (négociation consommateur) et sort")
    # `--root` partagé par TOUTES les sous-commandes (parent parser) → `taskmap context foo --root .` marche
    # (forme naturelle), pas seulement `taskmap --root . context foo`.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", help="racine du vault/repo cible (défaut : repère .taskmap.toml/.git "
                                       "depuis le cwd, ou $TASKMAP_ROOT)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    ctx = sub.add_parser("context", parents=[common], help="les 3 liaisons STAMP d'une task")
    ctx.add_argument("slug", help="slug de la task (id)")
    ctx.set_defaults(func=_cmd_context)

    lk = sub.add_parser("link", parents=[common], help="pose un slot STAMP sur une task (écriture)")
    lk.add_argument("slug")
    lk.add_argument("anchors", nargs="+",
                    help="ancres à poser (ex. epic=…, blueprint=…:applies, serves=a,b)")
    lk.add_argument("--dry-run", action="store_true", help="montre le diff sans écrire (fichier intact)")
    lk.set_defaults(func=_cmd_link)

    ulk = sub.add_parser("unlink", parents=[common], help="retire un slot STAMP d'une task (écriture)")
    ulk.add_argument("slug")
    ulk.add_argument("anchors", nargs="+",
                     help="ancres à retirer (ex. serves=a pour retirer, ou 'epic' nu pour vider le slot)")
    ulk.add_argument("--dry-run", action="store_true", help="montre le diff sans écrire")
    ulk.set_defaults(func=_cmd_unlink)

    rl = sub.add_parser("rollup", parents=[common], help="agrège le travail sous une dimension (axis <nom>)")
    rl.add_argument("dimension", choices=["axis"], help="dimension d'agrégation (P0 : axis)")
    rl.add_argument("name", help="nom de la dimension (ex. un axe north-star)")
    rl.set_defaults(func=_cmd_rollup)

    dr = sub.add_parser("doctor", parents=[common], help="cohérence des liaisons STAMP")
    dr.set_defaults(func=_cmd_doctor)

    return ap


def main(argv=None) -> int:
    ap = build_parser()
    a = ap.parse_args(argv)
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
