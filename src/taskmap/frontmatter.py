"""frontmatter — parsing stdlib-pur du frontmatter YAML des fichiers de tasks.

Remplace `vault_content.split_frontmatter` (qui reposait sur PyYAML) pour tenir l'invariant de la famille
`-map` « zéro dépendance » (`dependencies=[]`). Ce n'est PAS un parseur YAML général : il couvre le
sous-ensemble EXACT présent dans le corpus de tasks (sondé) — block-maps, block-seqs (`- x` et `- clé: v`),
flow-seqs `[a, b]`, scalaires typés, chaînes quotées, commentaires inline. Les blocs littéraux/folded
(`|`/`>`), ancres et multi-documents sont HORS scope (absents du corpus).

Parité : les types résolus MIMENT PyYAML 1.1 (`safe_load`) — null / bool / int / timestamp — pour qu'un port
1:1 du moteur de graphe (`graph.py`) produise un index identique (cf. `tools/parity_check.py`). En
particulier une date ISO NON quotée devient un `datetime.date` (comme PyYAML) : `_s()` la re-`str()` à
l'identique côté record, et `evaluate_trigger` la voit comme non-`str` à l'identique (parité des deux côtés).
"""
from __future__ import annotations

import datetime as _dt
import re
from typing import Any

# Résolveurs implicites (sous-ensemble PyYAML 1.1 safe_load).
_NULL = frozenset({"", "~", "null", "Null", "NULL"})
_BOOL_TRUE = frozenset({"true", "True", "TRUE", "yes", "Yes", "YES", "on", "On", "ON"})
_BOOL_FALSE = frozenset({"false", "False", "FALSE", "no", "No", "NO", "off", "Off", "OFF"})
_INT_RE = re.compile(r"^[-+]?[0-9]+$")
_DATE_RE = re.compile(r"^([0-9]{4})-([0-9]{2})-([0-9]{2})$")
# clé d'entrée de map inline dans un item de séquence (`- when: task_done`) : clé puis `:` + espace/eol.
_MAP_ENTRY = re.compile(r"""^["']?[\w.\-/]+["']?\s*:(\s|$)""")
# en-tête d'un bloc scalaire : `clé: |`/`>` + chomping/indent (`-`, `+`, digits) + commentaire éventuel.
_BLOCK_KEY = re.compile(r"^(\s*)(.+?):[ \t]*([|>])([-+0-9]*)[ \t]*(#.*)?$")


def split_frontmatter(text: str) -> tuple[dict, str]:
    """(frontmatter dict, corps). Même frontière que l'ex-`vault_content.split_frontmatter` (home unique du
    parsing) : bloc `---\\n…\\n---` en tête, tolère l'absence. Un frontmatter non-map résout en {}."""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            fm = _parse(text[3:end])
            return (fm if isinstance(fm, dict) else {}), text[end + 4:]
    return {}, text


def load(text: str) -> Any:
    """Parse un document YAML COMPLET (sans fences `---`) → la valeur racine.

    Même sous-ensemble que `split_frontmatter` (block-maps/seqs, flow, scalaires typés, blocs `|`/`>`), mais
    pour un doc AUTONOME — un manifeste, pas un frontmatter. Réutilise le parseur récursif interne ; un doc
    vide résout en {}. Sert le manifeste north-star (`northstar.load_manifest`) sans ajouter de dépendance."""
    return _parse(text)


# --- tokenisation ------------------------------------------------------------------------------------------

def _strip_comment(raw: str) -> str:
    """Retire un commentaire `#…` — règle YAML : `#` amorce un commentaire s'il est en début de ligne ou
    précédé d'un blanc, et hors d'une chaîne quotée. Un `#` collé (ex. `a#b`) reste littéral."""
    out: list[str] = []
    quote: str | None = None
    prev_ws = True  # début de ligne ≡ précédé d'un blanc
    for ch in raw:
        if quote:
            out.append(ch)
            if ch == quote:
                quote = None
            prev_ws = False
            continue
        if ch in ('"', "'"):
            quote = ch
            out.append(ch)
            prev_ws = False
            continue
        if ch == "#" and prev_ws:
            break
        out.append(ch)
        prev_ws = ch in (" ", "\t")
    return "".join(out)


def _tokenize(s: str) -> list[tuple[int, str]]:
    """Lignes signifiantes → (indent, contenu-trimé). Blanches et commentaires purs éliminés."""
    out: list[tuple[int, str]] = []
    for raw in s.split("\n"):
        line = _strip_comment(raw)
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        out.append((indent, line.strip()))
    return out


# --- parsing bloc ------------------------------------------------------------------------------------------

def _fold_lines(lines: list[str]) -> str:
    """Repli folded (`>`) : au sein d'un paragraphe, un saut de ligne devient un espace ; une ligne blanche
    devient un saut de ligne. Cas courant (paragraphe unique) → lignes jointes par ' '."""
    parts: list[str] = []
    prev_blank = True
    for ln in lines:
        if ln == "":
            parts.append("\n")
            prev_blank = True
        else:
            if not prev_blank:
                parts.append(" ")
            parts.append(ln)
            prev_blank = False
    return "".join(parts)


def _dq_escape(s: str) -> str:
    """Échappe une chaîne pour la ré-émettre en double-quote (réversible par `_unquote_str`)."""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")


def _collapse_block_scalars(s: str) -> str:
    """Pré-passe : réécrit tout bloc scalaire (`clé: |`/`>` + contenu indenté) en un scalaire double-quoté
    équivalent, AVANT tokenisation (les blocs préservent l'indentation et les lignes blanches, que la
    tokenisation détruirait). Miment PyYAML : littéral `|` (sauts conservés) / folded `>` (repli) + chomping
    `-` (strip) / `+` (keep) / défaut (clip : un seul saut final)."""
    lines = s.split("\n")
    out: list[str] = []
    i, n = 0, len(lines)
    while i < n:
        m = _BLOCK_KEY.match(lines[i])
        if not m:
            out.append(lines[i])
            i += 1
            continue
        indent_str, key, style, mods = m.group(1), m.group(2), m.group(3), m.group(4)
        key_indent = len(indent_str)
        explicit_indent: int | None = None
        chomp = ""
        for ch in mods:
            if ch in "+-":
                chomp = ch
            elif ch.isdigit():
                explicit_indent = key_indent + int(ch)
        # contenu : lignes suivantes blanches OU indentées > key_indent
        j = i + 1
        content: list[str] = []
        while j < n:
            ln = lines[j]
            if ln.strip() == "":
                content.append("")
                j += 1
                continue
            if (len(ln) - len(ln.lstrip(" "))) <= key_indent:
                break
            content.append(ln)
            j += 1
        block_indent = explicit_indent
        if block_indent is None:
            block_indent = next((len(ln) - len(ln.lstrip(" ")) for ln in content if ln), key_indent + 1)
        dedented = [ln[block_indent:] if len(ln) >= block_indent else "" for ln in content]
        body = "\n".join(dedented) if style == "|" else _fold_lines(dedented)
        body = body.rstrip("\n")
        if not any(dedented):
            body = ""
        elif chomp == "+":
            body += "\n" * sum(1 for _ in _trailing_blanks(dedented))
        elif chomp != "-":
            body += "\n"                       # clip (défaut) : un seul saut final
        out.append(f'{indent_str}{key}: "{_dq_escape(body)}"')
        i = j
    return "\n".join(out)


def _trailing_blanks(lines: list[str]):
    for ln in reversed(lines):
        if ln == "":
            yield ln
        else:
            break


def _parse(s: str) -> Any:
    toks = _tokenize(_collapse_block_scalars(s))
    if not toks:
        return {}
    val, _ = _parse_block(toks, 0, toks[0][0])
    return val


def _parse_block(toks: list[tuple[int, str]], i: int, indent: int) -> tuple[Any, int]:
    content = toks[i][1]
    if content == "-" or content.startswith("- "):
        return _parse_seq(toks, i, indent)
    return _parse_map(toks, i, indent)


def _parse_map(toks: list[tuple[int, str]], i: int, indent: int) -> tuple[dict, int]:
    result: dict = {}
    n = len(toks)
    while i < n:
        ind, content = toks[i]
        if ind < indent:
            break
        if ind > indent:               # ligne sur-indentée hors bloc reconnu (fail-soft) : ignorée
            i += 1
            continue
        if content == "-" or content.startswith("- "):
            break                      # une séquence au niveau map : ce n'est pas une map
        key, sep, rest = content.partition(":")
        if not sep:                    # ligne sans `:` dans une map (fail-soft) : ignorée
            i += 1
            continue
        k = _unquote_key(key.strip())
        rest = rest.strip()
        i += 1
        if rest == "":
            if i < n and toks[i][0] > indent:
                val, i = _parse_block(toks, i, toks[i][0])
            elif i < n and toks[i][0] == indent and (toks[i][1] == "-" or toks[i][1].startswith("- ")):
                val, i = _parse_seq(toks, i, indent)   # séquence sous-clé au MÊME indent (YAML valide)
            else:
                val = None
        else:
            val = _parse_flow_or_scalar(rest)
        result[k] = val
    return result, i


def _parse_seq(toks: list[tuple[int, str]], i: int, indent: int) -> tuple[list, int]:
    result: list = []
    n = len(toks)
    while i < n:
        ind, content = toks[i]
        if ind != indent or not (content == "-" or content.startswith("- ")):
            break
        item = content[2:].strip() if content.startswith("- ") else ""
        i += 1
        if item == "":                                 # item = bloc imbriqué plus profond
            if i < n and toks[i][0] > indent:
                val, i = _parse_block(toks, i, toks[i][0])
            else:
                val = None
            result.append(val)
        elif _MAP_ENTRY.match(item):                   # item = map, 1re clé inline (indent effectif +2)
            sub: list[tuple[int, str]] = [(indent + 2, item)]
            while i < n and toks[i][0] >= indent + 2:
                sub.append(toks[i])
                i += 1
            val, _ = _parse_map(sub, 0, indent + 2)
            result.append(val)
        else:
            result.append(_parse_flow_or_scalar(item))
    return result, i


# --- flow + scalaires --------------------------------------------------------------------------------------

def _split_commas(inner: str) -> list[str]:
    """Découpe sur les virgules de TÊTE (hors crochets/accolades/quotes)."""
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    quote: str | None = None
    for ch in inner:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in ('"', "'"):
            quote = ch
            buf.append(ch)
        elif ch in "[{":
            depth += 1
            buf.append(ch)
        elif ch in "]}":
            depth -= 1
            buf.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if buf:
        parts.append("".join(buf))
    return parts


def _parse_flow_or_scalar(s: str) -> Any:
    if s.startswith("["):
        return _parse_flow_seq(s)
    if s.startswith("{"):
        return _parse_flow_map(s)
    return _parse_scalar(s)


def _parse_flow_seq(s: str) -> list:
    end = s.rfind("]")
    inner = (s[1:end] if end != -1 else s[1:]).strip()
    if not inner:
        return []
    return [_parse_flow_or_scalar(p.strip()) for p in _split_commas(inner)]


def _parse_flow_map(s: str) -> dict:
    end = s.rfind("}")
    inner = (s[1:end] if end != -1 else s[1:]).strip()
    out: dict = {}
    if not inner:
        return out
    for part in _split_commas(inner):
        k, sep, v = part.partition(":")
        if sep:
            out[_unquote_key(k.strip())] = _parse_flow_or_scalar(v.strip())
    return out


def _parse_scalar(s: str) -> Any:
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return _unquote_str(s)
    return _resolve(s)


def _resolve(s: str) -> Any:
    """Résolution de type d'un scalaire NON quoté (parité PyYAML 1.1 sur le sous-ensemble utilisé)."""
    if s in _NULL:
        return None
    if s in _BOOL_TRUE:
        return True
    if s in _BOOL_FALSE:
        return False
    m = _DATE_RE.match(s)
    if m:
        try:
            return _dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return s
    if _INT_RE.match(s):
        return int(s)
    return s


def _unquote_key(k: str) -> str:
    if len(k) >= 2 and k[0] == k[-1] and k[0] in "\"'":
        return k[1:-1]
    return k


def _unquote_str(s: str) -> str:
    q = s[0]
    body = s[1:-1]
    if q == '"':
        # échappement double-quote MINIMAL (ne PAS passer par unicode_escape : casserait l'UTF-8/accents).
        return re.sub(r"\\(.)", lambda mo: {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}.get(
            mo.group(1), mo.group(1)), body)
    return body.replace("''", "'")   # single-quote YAML : seul `''` s'échappe
