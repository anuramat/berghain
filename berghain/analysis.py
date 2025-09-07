from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, FrozenSet, Iterable

import numpy as np


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
    sets: set[frozenset[str]] = set()
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

    attributes = tuple(sorted(seen))
    bits_to_set = tuple(
        frozenset(attributes[i] for i in range(len(attributes)) if (b >> i) & 1)
        for b in range(2 ** len(attributes))
    )
    # https://en.wikipedia.org/wiki/Categorical_distribution#Bayesian_inference_using_conjugate_prior
    # TODO: maybe make alpha depend on attribute
    alpha = 0.5
    proba = np.asarray(
        [
            ((counts[attrset] + alpha) / (total + alpha * (2 ** len(attributes))))
            for attrset in bits_to_set
        ]
    )

    return {
        "attributes": attributes,
        "total": total,
        "counts": dict(counts),
        "sets": tuple(sorted(list(sets))),
        "proba": proba,
        "bits_to_set": bits_to_set,
    }
