class BaseStrategy:
    min_required: dict[str, int]
    relative_frequencies: dict[str, float]
    correlations: dict[str, dict[str, float]]

    def __init__(self, constraints: list[dict], attribute_statistics: dict):
        self.min_required = {c["attribute"]: c["minCount"] for c in (constraints or [])}
        self.relative_frequencies = (attribute_statistics or {}).get(
            "relativeFrequencies", {}
        )
        self.correlations = (attribute_statistics or {}).get("correlations", {})
