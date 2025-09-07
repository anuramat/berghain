from abc import ABC, abstractmethod

from .distribution import OnlineDistribution

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
    distribution: OnlineDistribution  # online joint distribution learning

    def __init__(
        self, scenario: int, constraints: list[dict], attribute_statistics: dict
    ):
        self.min_required = {c["attribute"]: c["minCount"] for c in (constraints or [])}
        self.relative_frequencies = (attribute_statistics or {}).get(
            "relativeFrequencies", {}
        )
        self.correlations = (attribute_statistics or {}).get("correlations", {})
        self.max_rejections = MAX_REJECTIONS[scenario]
        
        # Initialize online distribution with API constraints
        self.distribution = OnlineDistribution(
            marginals=self.relative_frequencies,
            correlations=self.correlations
        )
    
    def update_distribution(self, attrs: dict[str, bool]) -> None:
        """Update the joint distribution with observed person attributes."""
        self.distribution.update(attrs)

    @abstractmethod
    def decide(self, attrs: dict[str, bool]) -> bool: ...
