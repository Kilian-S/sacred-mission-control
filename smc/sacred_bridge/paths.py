"""Locations of the sacred repo, the thesis directory, and this app's own data.

The sacred repo is READ-ONLY (a separate agent commits there while this app
runs). This module never writes anywhere except EXPORT_DIR.
"""

from __future__ import annotations

import os
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2]


def _resolve_sacred_root() -> Path:
    """Find the sacred data. Honour SACRED_ROOT if set, else prefer a sibling
    ``../sacred`` (the development and downloadable-bundle layout); fall back to
    ``./sacred`` inside the app (the git-clone + data-download layout)."""
    env = os.environ.get("SACRED_ROOT")
    if env:
        return Path(env).resolve()
    sibling = APP_ROOT.parent / "sacred"
    inside = APP_ROOT / "sacred"
    if not (sibling / "experiments").is_dir() and (inside / "experiments").is_dir():
        return inside.resolve()
    return sibling.resolve()


SACRED_ROOT = _resolve_sacred_root()
THESIS_ROOT = Path(
    os.environ.get("SACRED_THESIS_ROOT", APP_ROOT.parents[1] / "thesis")
).resolve()

DATA_DIR = APP_ROOT / "data"
EXPORT_DIR = Path.home() / "Desktop" / "sacred-mc-exports"

EXPERIMENTS_DIR = SACRED_ROOT / "experiments"
RUNS_DIR = SACRED_ROOT / "models" / "runs"
MAPS_DIR = SACRED_ROOT / "data" / "maps"
TB_DIR = SACRED_ROOT / "logs" / "tb_runs"
SCRATCH_DIR = SACRED_ROOT / "scratch"
ASSETS_DIR = SACRED_ROOT / "assets"


def sacred_available() -> bool:
    return EXPERIMENTS_DIR.is_dir()


def thesis_available() -> bool:
    return THESIS_ROOT.is_dir()


_sys_path_added = False


def ensure_sacred_importable() -> None:
    """Make `src.*` and `scripts.*` from the sacred repo importable, lazily."""
    global _sys_path_added
    if not _sys_path_added:
        import sys

        p = str(SACRED_ROOT)
        if p not in sys.path:
            sys.path.insert(0, p)
        _sys_path_added = True
