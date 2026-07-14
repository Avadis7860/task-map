"""anchors — grammaire d'ancre STAMP `clé=valeur[:posture]` → `StampEdit`.

Isolée du module `cli` (qui importe le package root pour l'enveloppe) afin d'être **re-exportable** par
`taskmap` sans import circulaire. **API publique** : le wrapper vault `task_map.py` (P6) la consomme pour
parser les ancres à l'identique, au lieu de dupliquer la grammaire ([[feedback-no-redundant-capability]]).
"""
from __future__ import annotations

from taskmap.authoring import AuthoringError, StampEdit

_LIST_KEYS: tuple[str, ...] = ("serves", "unblocks", "template")
_ANCHOR_KEYS: tuple[str, ...] = ("epic", "blueprint", *_LIST_KEYS)


def build_stamp_edit(tokens: list[str], *, removing: bool) -> StampEdit:
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
