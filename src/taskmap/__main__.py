"""Permet `python -m taskmap …` (équivalent du console_script `taskmap`)."""
from __future__ import annotations

from taskmap.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
