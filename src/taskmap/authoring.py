"""authoring — pose/mute les slots STAMP dans le frontmatter d'une task (le volet WRITE de STAMP).

Écart délibéré vs l'invariant read-only de la famille `-map`, **confiné** ici (module séparé du moteur de
lecture `graph`/`classify`). Le contrat de mutation est tranché dans la décision vault
`corpus/decision/projects/2026-07-14--stamp-write-model-contract.md` (deep-dive
`stamp-write-model-reconcile`). Invariants tenus :

- **Édition chirurgicale ligne-à-ligne**, jamais de yaml round-trip. Le parseur `frontmatter` est *lossy*
  (drop commentaires/blancs, réécrit les blocs `|`/`>`, coerce les dates) : re-dumper bruiterait le git. On ne
  touche QUE les lignes des slots mutés ; corps, commentaires, styles et clés voisines restent intacts.
- **Ordre canonique** : les slots STAMP forment un bloc inséré juste après `depends_on`, dans l'ordre
  `epic · serves · unblocks · blueprint · template` (cf. `_CANON_ORDER`).
- **`axis` jamais écrit** — dérivé du rollup épic→axe (I1) ; `StampEdit` n'a structurellement aucun champ.
- **Idempotence** : sémantique déclarative d'état-cible ; `plan_edit` calcule le texte-cible, `changed` est un
  simple `new != old`. Ré-appliquer le même edit → `changed=False`, aucune écriture.
- **Séparation pur/impur (I4)** : `plan_edit(text, edit) -> EditPlan` est **pur** (zéro I/O, testé par
  `selftest`) ; `apply_edit(path, plan)` est la seule coquille impure (écriture **atomique**, no-op si
  inchangé). Le motor **n'écrit que le fichier, jamais de commit** — le vault s'édite par git.
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from pathlib import Path

from taskmap.core import atomic
from taskmap.frontmatter import split_frontmatter

# Ordre canonique COMPLET des clés de frontmatter (TEMPLATE.md du vault) + le bloc STAMP inséré juste après
# `depends_on`, avant `phases`/`env`. Sert à placer un slot absent au bon rang (avant la 1re clé de rang >).
_CANON_ORDER: tuple[str, ...] = (
    "id", "status", "priority", "created", "updated", "service", "category", "owner",
    "related_decisions", "related_catalogs", "tags", "depends_on",
    "epic", "serves", "unblocks", "blueprint", "template",  # ← bloc STAMP
    "phases", "env", "spawned_by", "trigger", "dod_criteria", "next", "persona",
)
_RANK: dict[str, int] = {k: i for i, k in enumerate(_CANON_ORDER)}

_SCALAR_SLOTS: tuple[str, ...] = ("epic", "blueprint")
_LIST_SLOTS: tuple[str, ...] = ("serves", "unblocks", "template")
_STAMP_SLOTS: tuple[str, ...] = _SCALAR_SLOTS + _LIST_SLOTS  # NE CONTIENT JAMAIS "axis" (dérivé, I1).
_POSTURES: frozenset[str] = frozenset({"applies", "tests", "updates-candidate"})

# Ligne de clé top-level dans le frontmatter (colonne 0, `clé:`), par opposition aux continuations (lignes
# indentées, items `- …`, commentaires `#…`, lignes vides) qui appartiennent à la clé précédente.
_TOP_KEY = re.compile(r"^([A-Za-z_][\w.\-/]*)\s*:")


class AuthoringError(ValueError):
    """Frontmatter malformé (absent ou non terminé) — on refuse d'écrire plutôt que de corrompre."""


@dataclass(frozen=True)
class StampEdit:
    """Mutation déclarative des slots STAMP. Champs à `None`/vides = slot laissé INTACT (pas de reformatage).

    - `epic` / `blueprint` : set (écrase). `blueprint` = `(id, posture)`, `posture ∈ _POSTURES`.
    - `*_add` / `*_remove` : union / retrait sur les listes (`serves`/`unblocks`/`template`).
    - `clear` : noms de slots à VIDER (scalaire → ligne retirée ; liste → vidée puis retirée si vide).

    Aucun champ `axis` : le slot dérivé n'est structurellement pas écrivable.
    """

    epic: str | None = None
    blueprint: tuple[str, str] | None = None
    serves_add: tuple[str, ...] = ()
    serves_remove: tuple[str, ...] = ()
    unblocks_add: tuple[str, ...] = ()
    unblocks_remove: tuple[str, ...] = ()
    template_add: tuple[str, ...] = ()
    template_remove: tuple[str, ...] = ()
    clear: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class EditPlan:
    """Résultat pur de `plan_edit` : le texte-cible, s'il diffère, et le diff unifié (vide si inchangé)."""

    new_text: str
    changed: bool
    diff: str


class _Skip:
    """Sentinelle « ne pas toucher ce slot » — distincte de `None`, qui signifie « retirer la ligne »."""


_SKIP = _Skip()


# --- cœur pur (zéro I/O) ------------------------------------------------------------------------------------

def plan_edit(text: str, edit: StampEdit) -> EditPlan:
    """Calcule le texte-cible après application de `edit`, sans aucune I/O (I4, testable in-memory).

    Édition chirurgicale : ne réécrit que les lignes des slots effectivement mutés. Lève `AuthoringError` si
    `text` n'a pas de frontmatter `---…---` en tête.
    """
    fm, _body = split_frontmatter(text)
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        raise AuthoringError("pas de frontmatter YAML en tête")
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        raise AuthoringError("frontmatter non terminé")

    fm_lines = lines[1:end]  # région éditable (entre les deux fences)
    for slot in _STAMP_SLOTS:  # ordre canonique → insertions successives restent triées
        rendered = _desired_line(slot, fm, edit)
        if isinstance(rendered, _Skip):
            continue
        _place_slot(fm_lines, slot, rendered)

    new_text = "\n".join(["---", *fm_lines, *lines[end:]])
    changed = new_text != text
    diff = "" if not changed else "".join(
        difflib.unified_diff(
            text.splitlines(keepends=True), new_text.splitlines(keepends=True),
            fromfile="a", tofile="b",
        )
    )
    return EditPlan(new_text=new_text, changed=changed, diff=diff)


def _desired_line(slot: str, fm: dict, edit: StampEdit) -> str | None | _Skip:
    """État cible d'un slot : une ligne rendue (SET), `None` (retirer), ou `_SKIP` (laisser intact)."""
    if slot in _SCALAR_SLOTS:
        if slot in edit.clear:
            return None
        if slot == "epic" and edit.epic is not None:
            return f"epic: {edit.epic}"
        if slot == "blueprint" and edit.blueprint is not None:
            bid, posture = edit.blueprint
            if posture not in _POSTURES:
                raise AuthoringError(f"posture invalide: {posture!r} (∈ {sorted(_POSTURES)})")
            return f"blueprint: {{id: {bid}, posture: {posture}}}"
        return _SKIP
    # slots-liste
    add, remove = _list_ops(slot, edit)
    if slot not in edit.clear and not add and not remove:
        return _SKIP
    current = fm.get(slot)
    existing = tuple(str(x) for x in current) if isinstance(current, list) else ()
    new_items = () if slot in edit.clear else _merge_list(existing, add, remove)
    if not new_items:
        return None
    return f"{slot}: [{', '.join(new_items)}]"


def _list_ops(slot: str, edit: StampEdit) -> tuple[tuple[str, ...], tuple[str, ...]]:
    return {
        "serves": (edit.serves_add, edit.serves_remove),
        "unblocks": (edit.unblocks_add, edit.unblocks_remove),
        "template": (edit.template_add, edit.template_remove),
    }[slot]


def _merge_list(existing: tuple[str, ...], add: tuple[str, ...], remove: tuple[str, ...]) -> tuple[str, ...]:
    """Union ordonnée (existants d'abord, puis nouveaux) moins les retraits ; dédupliquée, déterministe."""
    out = list(existing)
    for a in add:
        if a not in out:
            out.append(a)
    return tuple(x for x in out if x not in remove)


def _place_slot(fm_lines: list[str], slot: str, rendered: str | None) -> None:
    """Applique l'état cible d'un slot au bloc de frontmatter (mute `fm_lines` en place).

    `rendered=None` → retire la ligne si présente ; sinon remplace la ligne existante ou l'insère au rang
    canonique (juste avant la 1re clé de rang supérieur, sinon en fin de frontmatter).
    """
    spans = _key_spans(fm_lines)
    cur = next((s for s in spans if s[0] == slot), None)
    if rendered is None:
        if cur is not None:
            del fm_lines[cur[1]:cur[2]]
        return
    if cur is not None:  # remplace tout le span (normalise un éventuel bloc multi-ligne en une ligne flow)
        fm_lines[cur[1]:cur[2]] = [rendered]
        return
    rank = _RANK[slot]
    insert_at = len(fm_lines)
    for key, start, _stop in spans:
        if _RANK.get(key, len(_CANON_ORDER)) > rank:
            insert_at = start
            break
    fm_lines.insert(insert_at, rendered)


def _key_spans(fm_lines: list[str]) -> list[tuple[str, int, int]]:
    """(clé top-level, début, fin-exclue) par clé ; les continuations étendent la clé courante."""
    spans: list[list] = []
    for idx, line in enumerate(fm_lines):
        m = _TOP_KEY.match(line)
        if m:
            spans.append([m.group(1), idx, idx + 1])
        elif spans:
            spans[-1][2] = idx + 1
    return [(k, s, e) for k, s, e in spans]


# --- coquille impure (la seule qui écrit) -------------------------------------------------------------------

def apply_edit(path: Path | str, plan: EditPlan) -> bool:
    """Écrit `plan.new_text` dans `path` de façon atomique. No-op (retourne False) si `not plan.changed`.

    N'exécute JAMAIS de git : le fichier dirty non-committé est le hand-off vers la couche git/forgemaster.
    """
    if not plan.changed:
        return False
    atomic.write_text(path, plan.new_text)
    return True


# --- selftest in-module (I4) --------------------------------------------------------------------------------

_SELFTEST_DOC = """---
id: demo-task
status: active
priority: P1
created: 2026-07-14
updated: 2026-07-14
depends_on: [amont-a]
env: vault
next: "action : voir `truc` et [[machin]]"
---

# Objectif final

Corps préservé.
"""


def selftest() -> None:
    """Vérifie pose/mute/idempotence/préservation-corps sur un frontmatter in-memory (aucun I/O)."""
    # pose epic + une liste : placés au rang canonique (après depends_on, avant env), corps intact.
    p1 = plan_edit(_SELFTEST_DOC, StampEdit(epic="ROADMAP-x", serves_add=("t-1", "t-2")))
    assert p1.changed
    assert "epic: ROADMAP-x" in p1.new_text
    assert "serves: [t-1, t-2]" in p1.new_text
    assert "# Objectif final\n\nCorps préservé." in p1.new_text
    assert '"action : voir `truc` et [[machin]]"' in p1.new_text  # next: intact
    di = p1.new_text.index("depends_on:")
    assert di < p1.new_text.index("epic:") < p1.new_text.index("serves:") < p1.new_text.index("\nenv:")

    # idempotence : ré-appliquer le même edit sur le résultat = no-op.
    assert plan_edit(p1.new_text, StampEdit(epic="ROADMAP-x", serves_add=("t-1", "t-2"))).changed is False

    # union de liste (ajout d'un existant = no-op ; ajout d'un neuf = ordonné après).
    assert plan_edit(p1.new_text, StampEdit(serves_add=("t-1",))).changed is False
    assert "serves: [t-1, t-2, t-3]" in plan_edit(p1.new_text, StampEdit(serves_add=("t-3",))).new_text

    # retrait total d'une liste → ligne retirée.
    p2 = plan_edit(p1.new_text, StampEdit(serves_remove=("t-1", "t-2")))
    assert "serves:" not in p2.new_text and "epic: ROADMAP-x" in p2.new_text

    # blueprint flow-map + posture validée.
    p3 = plan_edit(_SELFTEST_DOC, StampEdit(blueprint=("deterministic-tooling-gate", "applies")))
    assert "blueprint: {id: deterministic-tooling-gate, posture: applies}" in p3.new_text
    try:
        plan_edit(_SELFTEST_DOC, StampEdit(blueprint=("bp", "bogus")))
        raise AssertionError("posture invalide acceptée")
    except AuthoringError:
        pass

    # clear d'un scalaire → retire la ligne.
    assert "epic:" not in plan_edit(p1.new_text, StampEdit(clear=frozenset({"epic"}))).new_text

    # axis n'est structurellement pas écrivable.
    assert "axis" not in _STAMP_SLOTS
    assert not hasattr(StampEdit(), "axis")

    # frontmatter absent → refus net.
    try:
        plan_edit("pas de frontmatter", StampEdit(epic="x"))
        raise AssertionError("frontmatter absent accepté")
    except AuthoringError:
        pass

    print("authoring.selftest: OK")


if __name__ == "__main__":
    selftest()
