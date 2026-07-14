#!/usr/bin/env python3
"""parity_check — preuve de non-régression du port P1 (moteur stdlib `taskmap` vs moteur PyYAML du vault).

Le moteur `taskmap.graph`+`classify` est un port 1:1 de `.claude/scripts/lib/vault_tasks.py`, avec le parsing
frontmatter ré-implémenté en stdlib pur (`taskmap.frontmatter`, sans PyYAML). Ce harnais PROUVE qu'ils
produisent un graphe IDENTIQUE sur le corpus de tasks réel du vault :

  - référence : `vault_tasks.load_tasks`+`classify` exécuté sous le venv scripts du vault (il a PyYAML),
    via sous-process → dump JSON canonique sur stdout ;
  - candidat  : `taskmap.load_tasks`+`classify` in-process (stdlib pur) → même dump canonique ;
  - diff : les deux chaînes DOIVENT être identiques (sinon on liste les tasks/warnings divergents).

Ce n'est PAS un test pytest permanent (il exige le vault) : c'est la vérif one-shot de P1. Les fixtures
synthétiques sous `tests/` sont le filet permanent.

Usage :
    python tools/parity_check.py --vault /home/avadis/Documents/Vault-V1
    (--vault-python par défaut : <vault>/.claude/scripts/.venv/bin/python)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

# `today` figé → les triggers date_after sont déterministes des deux côtés.
TODAY = "2026-07-14"

# Script de référence exécuté sous le python du vault (avec PyYAML). Émet le dump canonique sur stdout.
_REF_SRC = '''
import json, sys
sys.path.insert(0, {lib!r})
import vault_tasks as vt
root = __import__("pathlib").Path({vault!r})
index, warnings = vt.load_tasks(root)
classified = vt.classify(index, root, {today!r})
print(json.dumps({{"warnings": warnings, "tasks": classified}},
                 sort_keys=True, ensure_ascii=False, default=str, indent=2))
'''


def _canon_candidate(vault: Path) -> str:
    """Dump canonique du moteur `taskmap` (in-process, stdlib pur)."""
    import taskmap
    index, warnings = taskmap.load_tasks(vault)
    classified = taskmap.classify(index, vault, TODAY)
    return json.dumps({"warnings": warnings, "tasks": classified},
                      sort_keys=True, ensure_ascii=False, default=str, indent=2)


def _canon_reference(vault: Path, vault_python: Path) -> str:
    """Dump canonique du moteur vault de référence (sous-process, venv scripts du vault, PyYAML)."""
    lib = str(vault / ".claude" / "scripts" / "lib")
    src = _REF_SRC.format(lib=lib, vault=str(vault), today=TODAY)
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(src)
        ref_script = f.name
    try:
        out = subprocess.run([str(vault_python), ref_script], capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        sys.stderr.write("échec du dump de référence (moteur vault) :\n" + e.stderr + "\n")
        raise
    finally:
        Path(ref_script).unlink(missing_ok=True)
    return out.stdout.rstrip("\n")


def _diff(ref: str, cand: str) -> list[str]:
    """Diffe deux dumps canoniques (warnings + tasks). Retourne les lignes de divergence ([] si parité)."""
    r, c = json.loads(ref), json.loads(cand)
    out: list[str] = []
    rw, cw = r["warnings"], c["warnings"]
    if rw != cw:
        only_ref = [w for w in rw if w not in cw]
        only_cand = [w for w in cw if w not in rw]
        out.append(f"warnings divergents : {len(only_ref)} en réf seule, {len(only_cand)} en candidat seul")
        out += [f"  - réf-seul : {w}" for w in only_ref[:20]]
        out += [f"  + cand-seul : {w}" for w in only_cand[:20]]
    rt, ct = r["tasks"], c["tasks"]
    rk, ck = set(rt), set(ct)
    if rk != ck:
        out.append(f"ids divergents : réf-seul={sorted(rk - ck)[:20]} cand-seul={sorted(ck - rk)[:20]}")
    for tid in sorted(rk & ck):
        if rt[tid] != ct[tid]:
            out.append(f"record divergent : {tid}")
            for key in sorted(set(rt[tid]) | set(ct[tid])):
                if rt[tid].get(key) != ct[tid].get(key):
                    out.append(f"    .{key} : réf={rt[tid].get(key)!r} vs cand={ct[tid].get(key)!r}")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="preuve de non-régression du port du moteur de graphe (P1)")
    ap.add_argument("--vault", required=True, help="racine du vault (corpus de tasks de référence)")
    ap.add_argument("--vault-python", default=None,
                    help="python du venv scripts du vault (défaut : <vault>/.claude/scripts/.venv/bin/py)")
    a = ap.parse_args(argv)
    vault = Path(a.vault).expanduser().resolve()
    default_vpy = vault / ".claude" / "scripts" / ".venv" / "bin" / "python"
    vpy = Path(a.vault_python) if a.vault_python else default_vpy

    ref = _canon_reference(vault, vpy)
    cand = _canon_candidate(vault)
    diffs = _diff(ref, cand)

    n = len(json.loads(cand)["tasks"])
    if not diffs:
        print(f"✓ PARITÉ : moteur stdlib == moteur vault sur {n} tasks (diff vide).")
        return 0
    print(f"✗ DIVERGENCE sur {n} tasks — {len(diffs)} lignes :")
    for line in diffs[:120]:
        print(line)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
