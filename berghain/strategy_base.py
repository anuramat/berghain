from abc import ABC, abstractmethod
from pathlib import Path

from .analysis import load_stats, scenario_to_path

MAX_REJECTIONS: dict[int, int] = {
    # depending on scenario
    1: 800,
    2: 5000,
    3: 6000,
}


class BaseStrategy(ABC):
    min_required: dict[str, int]
    relative_frequencies: dict[str, float]
    correlations: dict[str, dict[str, float]]
    max_rejections: int
    stats: dict | None  # counts from previous runs for joint estimation

    def __init__(
        self, scenario: int, constraints: list[dict], attribute_statistics: dict
    ):
        self.min_required = {c["attribute"]: c["minCount"] for c in (constraints or [])}
        self.relative_frequencies = (attribute_statistics or {}).get(
            "relativeFrequencies", {}
        )
        self.correlations = (attribute_statistics or {}).get("correlations", {})
        self.max_rejections = MAX_REJECTIONS[scenario]
        self.stats = load_stats(scenario_to_path(scenario))

    @abstractmethod
    def decide(self, attrs: dict[str, bool]) -> bool: ...
