"""Tolerant readers for sacred's run artefacts (models/runs/*).

The sacred repo is a growing, occasionally mid-write data source: another agent
commits new results while this app runs. Every reader here returns a typed
result and treats unreadable/partial JSON as "unavailable right now" (one retry,
then skip), never an exception.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .paths import RUNS_DIR

# history tuple layouts, decoded from the writing scripts (see DATA_MAP.md §2)
MULTICONVOY_HISTORY_FIELDS = (
    "sortie", "expl", "expl_tap", "alpha_leader", "alpha_foll",
    "stack_rate", "follow_rate", "H_lead", "H_foll", "t_train_s", "t_eval_s",
)
INTERDICTION_HISTORY_FIELDS = (
    "sortie", "expl_policy", "expl_tap", "expl_window", "expl_avg",
    "alpha", "policy_entropy",
)
GENERALIST_HISTORY_FIELDS = (
    "sortie", "train_ratio", "test_ratio", "test_ratios", "route_feat_w",
    "alpha_leader", "alpha_foll",
)
B1LITE_HISTORY_FIELDS = ("sortie", "eval_loss", "_pad")


@dataclass
class RunFile:
    path: Path
    data: dict[str, Any] | None
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.data is not None


def read_json(path: Path, retries: int = 1, retry_delay: float = 0.4) -> RunFile:
    """Read one JSON file, tolerating a concurrent partial write."""
    for attempt in range(retries + 1):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return RunFile(path=path, data=json.load(fh))
        except FileNotFoundError:
            return RunFile(path=path, data=None, error="missing")
        except (json.JSONDecodeError, OSError) as exc:
            if attempt < retries:
                time.sleep(retry_delay)
                continue
            return RunFile(path=path, data=None, error=f"unreadable: {exc}")
    return RunFile(path=path, data=None, error="unreachable")


def family_dir(family: str) -> Path:
    return RUNS_DIR / family


def list_family_jsons(family: str) -> list[Path]:
    d = family_dir(family)
    if not d.is_dir():
        return []
    return sorted(p for p in d.glob("*.json"))


def list_checkpoints(family: str, stem: str) -> list[Path]:
    """Per-eval actor checkpoints for e.g. family='gen13_lock', stem='seed0'."""
    d = family_dir(family) / f"{stem}_ckpts"
    if not d.is_dir():
        return []

    def ep(p: Path) -> int:
        try:
            return int(p.stem.split("actor_ep")[1])
        except (IndexError, ValueError):
            return 0

    return sorted(d.glob("actor_ep*.pt"), key=ep)


@dataclass
class HistorySeries:
    """A run's history unpacked into named columns."""
    fields: tuple[str, ...]
    columns: dict[str, list[Any]] = field(default_factory=dict)

    @classmethod
    def from_rows(cls, rows: list, fields: tuple[str, ...]) -> "HistorySeries":
        cols: dict[str, list[Any]] = {f: [] for f in fields}
        for row in rows:
            for i, f in enumerate(fields):
                cols[f].append(row[i] if i < len(row) else None)
        return cls(fields=fields, columns=cols)

    def col(self, name: str) -> list[Any]:
        return self.columns.get(name, [])


def multiconvoy_result(data: dict) -> dict | None:
    """The nested result dict of a train_multiconvoy JSON, whichever arm shape."""
    for key in ("fleet_route", "sacred", "vanilla"):
        if isinstance(data.get(key), dict) and "history" in data[key]:
            return data[key]
    return None
