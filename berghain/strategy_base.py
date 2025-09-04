from abc import ABC, abstractmethod

MAX_REJECTIONS: dict[int, int] = {
    # depending on scenario
    1: 776,
    2: 3317,
    3: 4194,
}


class BaseStrategy(ABC):
    min_required: dict[str, int]
    relative_frequencies: dict[str, float]
    correlations: dict[str, dict[str, float]]
    max_rejections: int
    # Stores joint distribution estimate from logs (or None if unset)
    joint_estimate: dict | None

    def __init__(
        self, scenario: int, constraints: list[dict], attribute_statistics: dict
    ):
        self.min_required = {c["attribute"]: c["minCount"] for c in (constraints or [])}
        self.relative_frequencies = (attribute_statistics or {}).get(
            "relativeFrequencies", {}
        )
        self.correlations = (attribute_statistics or {}).get("correlations", {})
        self.max_rejections = MAX_REJECTIONS[scenario]
        self.joint_estimate = None

    @abstractmethod
    def decide(self, attrs: dict[str, bool]) -> bool: ...
