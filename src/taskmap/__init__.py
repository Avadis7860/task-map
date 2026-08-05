"""taskmap — moteur déterministe de liaison des tasks à leurs ancrages (protocole STAMP).

6ᵉ outil de la famille `-map` (code-map / docs-map / front-map / bundle-map / forgemaster-catalogs).
Matérialise
**STAMP** : la liaison vivante de toute task à ses ancrages — north-star (axe) et épic/backlog en aval,
blueprint/template en amont — au lieu d'une liste mtime plate. Distillé du moteur de graphe `vault_tasks.py`
du vault, rendu générique (aucun chemin en dur) et empaqueté.

Voir `docs/architecture.md` pour les couches et `docs/schema-contract.md` pour le contrat de sortie.

API publique stable (re-exports) : le moteur de graphe (P1) est exposé ici ; la logique CLI arrive en P5.
"""
from __future__ import annotations

from taskmap.anchors import build_stamp_edit
from taskmap.authoring import EditPlan, StampEdit, apply_edit, plan_edit
from taskmap.classify import classify, evaluate_dod_criteria, evaluate_trigger
from taskmap.config import Config
from taskmap.context import blueprint_verdict, build_context, doctor, extract_stamp, rollup_axis
from taskmap.graph import ENGINE, eff_prio, load_tasks, rank_ready
from taskmap.northstar import Manifest, axis_for_epic, load_manifest, validate

__all__ = ["ENGINE", "SCHEMA_VERSION", "Config", "EditPlan", "Manifest", "StampEdit", "__version__",
           "apply_edit", "axis_for_epic", "blueprint_verdict", "build_context", "build_stamp_edit",
           "classify", "doctor", "eff_prio", "evaluate_dod_criteria", "evaluate_trigger", "extract_stamp",
           "load_manifest", "load_tasks", "plan_edit", "rank_ready", "rollup_axis", "validate"]

__version__ = "0.1.0"

# Version du CONTRAT de schéma (enveloppe de sortie + modèle STAMP), distincte de la version du package.
# Évolution **additive** : bump mineur quand on AJOUTE un champ/slot (jamais de retrait/renommage d'un champ
# figé). Exposée par `taskmap --schema-version` et dans l'enveloppe de chaque verbe pour qu'un consommateur
# (hook session-start, forgemaster) négocie le contrat. Voir docs/schema-contract.md.
# 0.1.0 : squelette (P0) — enveloppe `{ok, schema_version}` + surface CLI figée (context/link/unlink/rollup/
# doctor, en stubs). Le modèle STAMP et le moteur de graphe arrivent en P1/P5 (bumps additifs à suivre).
SCHEMA_VERSION = "0.1.0"
