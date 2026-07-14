"""graph — moteur de graphe de tasks (READ-ONLY). Port de `vault_tasks.py` (`task-graph-v1`) du vault.

Charge les 3 buckets `tasks/{backlog,active,archive}` (rglob, reorg V2), construit le DAG `depends_on`,
dérive les arêtes de phases d'une umbrella, détecte les cycles, réconcilie les checklists d'épic. C'est la
moitié « chargement + structure » du moteur ; la classification d'état (`classify`, triggers, DoD) vit dans
`classify.py`. Port fidèle (comportement inchangé) avec deux dé-vaultisations :

  1. le parsing frontmatter passe de PyYAML (`vault_content.split_frontmatter`) au parseur stdlib interne
     (`taskmap.frontmatter`), pour tenir `dependencies=[]` (famille `-map`) ;
  2. le vocab métier (priorités/services/catégories) et l'emplacement des buckets (`.claude/tasks`) sont
     externalisés en `.taskmap.toml` via `taskmap.config.Config` (P2) — défauts permissifs si absent.

Restent ici les constantes de GRAMMAIRE du moteur (buckets, préfixe ROADMAP, statuts terminaux…) — pas le
vocab métier.

Classification (status = source de vérité, pas le dossier) : cf. `classify.py`. Déclencheurs (`trigger`) et
critères de DoD : cf. `classify.py`. Lecture seule : n'écrit rien, ne dérive aucun fichier.
"""
from __future__ import annotations

import re
from pathlib import Path

from taskmap.config import Config  # vocab (priorités/services/catégories) + emplacement des tasks
from taskmap.core.graph import detect_cycles  # cœur générique (détection de cycles) — re-exporté ici
from taskmap.frontmatter import split_frontmatter  # home unique du parsing frontmatter (stdlib-pur)

__all__ = [  # `detect_cycles` re-exportée du cœur pour la back-compat (imports historiques + test_graph)
    "detect_cycles",
    "load_tasks",
    "derive_phase_deps",
    "reconcile_epics",
]

ENGINE = "task-graph-v1"
BUCKETS = ("backlog", "active", "archive")   # ordre de charge : archive (done) gagne sur backlog
SKIP = {"README.md", "TEMPLATE.md", "TEMPLATE-workflow.md", "INDEX.md"}   # artefacts, pas des tasks
ROADMAP_PREFIX = "ROADMAP-"                  # un fichier ROADMAP-*.md est une umbrella (epic) par convention
BACKTICK_ID = re.compile(r"`([a-z0-9][a-z0-9-]+)`")   # `task-id` cité dans le corps d'un ROADMAP = enfant
# `env` = projet porteur de la tâche (vide/`vault` = orchestrateur). Validé À LA FRONTIÈRE de chargement
# (kebab-case strict) : valeur user-controlled, scopée en chemin en aval → garde anti-path-traversal unique
# ici. Invalide → warning + traité comme orchestrateur.
SAFE_ENV = re.compile(r"[a-z0-9][a-z0-9-]*")
# Le vocab MÉTIER (priorités ordonnées, services, catégories) et l'emplacement des tasks ne vivent plus ici :
# externalisés en `.taskmap.toml` via `taskmap.config.Config` (P2). Un repo sans config → défauts permissifs.
# Manifeste de PHASES d'une umbrella : liste ORDONNÉE d'étapes, chaque étape = liste d'ids parallèles.
# `derive_phase_deps` en dérive les arêtes séquentielles. Une ligne de checklist DoD d'épic
# `- [x] **P<n> — `slug`**` est parsée par CHECKLIST_ITEM pour la réconciliation case↔status.
CHECKLIST_ITEM = re.compile(r"^\s*- \[([ xX])\]\s*\*\*P\d+\s*[—–-]\s*`([a-z0-9][a-z0-9-]*)`")
# status par défaut DÉRIVÉ DU BUCKET quand le frontmatter n'en déclare pas.
BUCKET_DEFAULT_STATUS = {"backlog": "backlog", "active": "active", "archive": "done"}
TERMINAL_STATUS = {"done", "cancelled"}      # statuts terminaux ⇒ doivent vivre dans archive/


def _s(v) -> str:
    """Normalise une valeur frontmatter en str (une date non-quotée arrive en `datetime.date`)."""
    return "" if v is None else str(v)


def _normalize_phases(raw) -> tuple[list[list[str]] | None, list[str]]:
    """(steps|None, errs). Normalise le manifeste `phases:` d'une umbrella. Fail-soft : une valeur malformée
    est ignorée avec un motif, jamais un crash. Absent → (None, []). Chaque étape peut être un id scalaire
    (coercé en `[id]`) ou une liste d'ids kebab parallèles. Un id non-kebab / une étape non-liste → err."""
    if raw is None:
        return None, []
    errs: list[str] = []
    if not isinstance(raw, list):
        return None, [f"phases: liste d'étapes attendue (reçu {type(raw).__name__}) → ignoré"]
    steps: list[list[str]] = []
    for i, step in enumerate(raw):
        members = [step] if isinstance(step, str) else step
        if not isinstance(members, list):
            errs.append(f"phases: étape #{i + 1} n'est ni un id ni une liste → ignorée")
            continue
        clean: list[str] = []
        for m in members:
            ms = _s(m)
            if ms and SAFE_ENV.fullmatch(ms):
                clean.append(ms)
            else:
                errs.append(f"phases: id d'étape invalide {ms!r} (kebab-case attendu) → ignoré")
        steps.append(clean)
    return steps, errs


def _parse_phase_checklist(body: str) -> dict[str, bool]:
    """{slug -> coché} depuis les items `- [x] **P<n> — `slug`**` du corps d'une umbrella. {} si aucun."""
    out: dict[str, bool] = {}
    for ln in body.splitlines():
        m = CHECKLIST_ITEM.match(ln)
        if m:
            out[m.group(2)] = m.group(1).lower() == "x"
    return out


def load_tasks(root: Path, config: Config | None = None
               ) -> tuple[dict[str, dict], list[str]]:
    """id -> record, + warnings. archive écrase backlog (done fait foi). `config` porte le vocab (priorités/
    services/catégories) et l'emplacement des buckets (`tasks_subdir`) ; `None` → `Config.load(root)` (lit
    `<root>/.taskmap.toml`, défauts permissifs si absent). Vocab service/category VIDE ⇒ validation désactivée
    (aucun warning), pour qu'un repo tiers ne soit jamais réprimandé pour un vocab qu'il n'a pas déclaré."""
    root = Path(root)
    cfg = config if config is not None else Config.load(root)
    index: dict[str, dict] = {}
    warnings: list[str] = []
    tasks_dir = root.joinpath(*cfg.tasks_subdir)
    for bucket in BUCKETS:
        d = tasks_dir / bucket
        if not d.is_dir():
            continue
        # rglob (reorg V2) : découvre backlog/<service>/*.md et backlog/_inbox/*.md en plus du plat.
        for p in sorted(d.rglob("*.md")):
            if p.name in SKIP:
                continue
            try:
                fm, body = split_frontmatter(p.read_text(encoding="utf-8", errors="replace"))
            except Exception as e:  # noqa: BLE001 — un frontmatter illisible n'abat pas le graphe.
                warnings.append(f"frontmatter illisible : {p.relative_to(root).as_posix()} "
                                f"({type(e).__name__}) → ignoré")
                continue
            tid = _s(fm.get("id")) or p.stem
            raw_id = _s(fm.get("id"))
            if raw_id and raw_id != p.stem:
                warnings.append(f"slug≠id : fichier '{p.stem}.md' déclare id={raw_id!r} → un "
                                f"depends_on:[{p.stem}] pointera dans le vide (renommer le fichier ou l'id)")
            if not fm and bucket != "archive":
                warnings.append(f"frontmatter absent : {p.relative_to(root).as_posix()} "
                                f"(bucket={bucket}/) → compléter id/status")
            raw_status = _s(fm.get("status"))
            if raw_status and (raw_status in TERMINAL_STATUS) != (bucket == "archive"):
                fix = ("déplacer vers archive/" if raw_status in TERMINAL_STATUS
                       else "sortir d_archive/ ou corriger le status")
                warnings.append(f"incohérence bucket↔status : {tid} (status={raw_status}, "
                                f"bucket={bucket}/) → {fix}")
            # `blocked_by` = alias DÉPRÉCIÉ de `depends_on` : unionné (dédupliqué) au chargement pour qu'une
            # tâche porteuse ne sorte JAMAIS faussement READY ; warning de migration tant qu'il est porté.
            depends_on = list(fm.get("depends_on") or [])
            blocked_by = list(fm.get("blocked_by") or [])
            if blocked_by:
                warnings.append(f"champ déprécié 'blocked_by' sur {tid} → migrer vers depends_on "
                                f"(unionné en attendant)")
                depends_on = list(dict.fromkeys(depends_on + blocked_by))
            # `env` validé à la frontière (kebab-case strict) ; invalide → ignoré + warning, orchestrateur.
            env = _s(fm.get("env"))
            if env and not SAFE_ENV.fullmatch(env):
                warnings.append(f"env invalide '{env}' sur {tid} (kebab-case strict attendu) → "
                                f"ignoré, traité comme orchestrateur 'vault'")
                env = ""
            # titrage V2 : service/category validés contre le vocab fermé de la config (fail-soft → ignoré +
            # warning). Vocab VIDE (défaut permissif) ⇒ check désactivé : la valeur est gardée telle quelle.
            service = _s(fm.get("service"))
            if service and cfg.services and service not in cfg.services:
                warnings.append(f"service invalide '{service}' sur {tid} (hors vocab SERVICES) → ignoré")
                service = ""
            category = _s(fm.get("category"))
            if category and cfg.categories and category not in cfg.categories:
                warnings.append(f"category invalide '{category}' sur {tid} (hors vocab CATEGORIES) → ignoré")
                category = ""
            # priorité validée contre le vocab de la config (défaut non vide) : hors-vocab signalé → dernier.
            priority = _s(fm.get("priority")) or "P2"
            if priority not in cfg.prio:
                warnings.append(f"priority hors vocab '{priority}' sur {tid} (attendu ∈ {cfg.priorities}) → "
                                f"rangée en dernier")
            tags = list(fm.get("tags") or [])
            is_epic = "epic" in tags or p.name.startswith(ROADMAP_PREFIX)
            phases, phase_errs = _normalize_phases(fm.get("phases"))
            for perr in phase_errs:
                warnings.append(f"{perr} (sur {tid})")
            rec = {
                "id": tid,
                "status": raw_status or BUCKET_DEFAULT_STATUS.get(bucket, "backlog"),
                "priority": priority,
                "created": _s(fm.get("created")),
                "depends_on": depends_on,
                "tags": tags,
                "env": env,
                "service": service,     # titrage V2 (navigation) ; "" si absent/invalide
                "category": category,   # titrage V2 (type de travail) ; "" si absent/invalide
                "spawned_by": _s(fm.get("spawned_by")) or None,
                "trigger": fm.get("trigger"),   # condition de réveil (grammaire fermée) ; None = aucune
                "dod_criteria": fm.get("dod_criteria"),   # DoD machine-vérifiable ; None = régie prose
                "child_ids": BACKTICK_ID.findall(body) if p.name.startswith(ROADMAP_PREFIX) else [],
                "phases": phases,       # manifeste (étapes ordonnées = listes d'ids) ; None si non phasé
                "phase_deps": {},       # provenance des deps dérivées : {dep_id -> epic_id}
                "phase_checklist": _parse_phase_checklist(body) if is_epic else {},
                "bucket": bucket,
                "path": p.relative_to(root).as_posix(),
            }
            if tid in index:
                warnings.append(f"id dupliqué : {tid} ({index[tid]['bucket']}/ et {bucket}/) "
                                f"→ {bucket} retenu")
            index[tid] = rec   # bucket plus tardif (archive) gagne
    warnings += derive_phase_deps(index)
    return index, warnings


def derive_phase_deps(index: dict[str, dict]) -> list[str]:
    """Augmente IN-MÉMOIRE le `depends_on` des membres d'une umbrella phasée depuis son manifeste `phases:`.

    Chaque membre de l'étape N reçoit (union dédupliquée, ordre stable) les ids de toutes les étapes < N ;
    les membres d'une même étape ne dépendent PAS l'un de l'autre. Union AVEC les `depends_on` explicites
    (jamais d'écrasement). Provenance notée dans `rec['phase_deps']`. READ-ONLY disque. Fail-soft : un membre
    absent de l'index est signalé, sans dep fautive. Retourne les warnings."""
    warnings: list[str] = []
    for epic_id, epic in index.items():
        steps = epic.get("phases")
        if not steps:
            continue
        seen: list[str] = []            # ids des étapes déjà parcourues (prédécesseurs), ordre stable
        for step in steps:
            preds = list(seen)          # snapshot AVANT l'étape courante (parallélisme intra-étape)
            for member in step:
                m = index.get(member)
                if m is None:
                    warnings.append(f"phases: '{member}' cité par l'umbrella {epic_id} n'a AUCUN fichier "
                                    f"task → arête de phase ignorée")
                    continue
                for dep in preds:
                    if dep not in m["depends_on"]:
                        m["depends_on"].append(dep)
                    m["phase_deps"].setdefault(dep, epic_id)
            seen.extend(step)
    return warnings


def _children(index: dict[str, dict], epic_id: str) -> list[dict]:
    """Membres d'un épic (hors l'épic), via TROIS conventions unionnées : préfixe-id `<epic>-`, citation
    backtick (`child_ids`) filtrée contre les vraies tasks, et le manifeste `phases:` (autoritaire)."""
    pref = epic_id + "-"
    epic = index.get(epic_id, {})
    cited = set(epic.get("child_ids") or [])
    cited |= {i for step in (epic.get("phases") or []) for i in step}
    return [t for t in index.values()
            if t["id"] != epic_id and (t["id"].startswith(pref) or t["id"] in cited)]


def reconcile_epics(index: dict[str, dict]) -> list[str]:
    """Confronte la checklist DoD prose d'une umbrella (`phase_checklist`) au status RÉEL de ses sous-tasks.
    PUR, read-only. Retourne des warnings (dérive de PROSE → toujours warn, jamais error). Trois cas :
    `[x]`+status≠done (case en avance), `[ ]`+status==done (case en retard), slug listé sans fichier (info :
    non matérialisée). En prime : un membre `phases:` en `cancelled` → warning (bloquerait l'aval à vie)."""
    warns: list[str] = []
    for epic_id, epic in index.items():
        for slug, checked in (epic.get("phase_checklist") or {}).items():
            sub = index.get(slug)
            if sub is None:
                warns.append(f"réconciliation {epic_id} : phase `{slug}` listée dans la checklist mais "
                             f"AUCUNE task (info : non matérialisée)")
                continue
            st = sub["status"]
            if checked and st != "done":
                warns.append(f"réconciliation {epic_id} : `{slug}` coché [x] mais status={st} "
                             f"(case en avance sur le graphe)")
            elif not checked and st == "done":
                warns.append(f"réconciliation {epic_id} : `{slug}` est done mais case décochée [ ] "
                             f"(case en retard sur le graphe)")
        for step in (epic.get("phases") or []):
            for m in step:
                sub = index.get(m)
                if sub is not None and sub["status"] == "cancelled":
                    warns.append(f"réconciliation {epic_id} : `{m}` (membre du manifeste phases) est "
                                 f"cancelled → retirer du manifeste (bloquerait l'aval à vie)")
    return warns
