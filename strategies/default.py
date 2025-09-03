import json
import random

from berghain.strategy_base import BaseStrategy


class Strategy(BaseStrategy):
    def __init__(self, scenario, constraints, attribute_statistics):
        print(
            "strategy init:",
            json.dumps(
                {
                    "constraints": constraints,
                    "attributeStatistics": attribute_statistics,
                },
                separators=(",", ":"),
            ),
        )
        super().__init__(scenario, constraints, attribute_statistics)

    def decide(self, attrs: dict[str, bool]) -> bool:
        print("attrs:", json.dumps(attrs, separators=(",", ":")))
        return random.choice([True, False])
