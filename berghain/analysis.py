from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, FrozenSet, Iterable


def _collect_files(path: str) -> list[Path]:
    p = Path(path)
    if p.is_dir():
        return sorted(x for x in p.iterdir() if x.is_file() and x.suffix == ".txt")
    if p.is_file():
        return [p]
    return []


def scenario_to_path(scenario: int) -> str:
    return f"logs/scenario{scenario}"


def load_stats(path: str) -> dict | None:
    # TODO refactor: use an actual object instead of a dict
    """Load attribute counts from log files."""
    files = _collect_files(path)
    if not files:
        return None

    counts: Dict[FrozenSet[str], int] = defaultdict(int)
    seen: set[str] = set()
    attr_true: dict[str, int] = defaultdict(int)
    sets: set[frozenset] = set()
    total = 0

    for fp in files:
        try:
            with fp.open("r") as f:
                for line in f:
                    s = line.strip()
                    if not s:
                        continue
                    try:
                        obj = json.loads(s)
                    except Exception:
                        continue
                    if not isinstance(obj, dict):
                        continue
                    seen.update(obj.keys())
                    true_set = frozenset(k for k, v in obj.items() if v is True)
                    sets.add(true_set)
                    for k in true_set:
                        attr_true[k] += 1
                    counts[true_set] += 1
                    total += 1
        except FileNotFoundError:
            continue

    if total == 0:
        return None

    return {
        "attributes": tuple(sorted(seen)),
        "total": total,
        "counts": dict(counts),
        "sets": sets,
    }
