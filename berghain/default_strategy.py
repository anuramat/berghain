import json
import random

from .main import BaseStrategy


class DefaultStrategy(BaseStrategy):
    def __init__(self, constraints, attribute_statistics):
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
        super().__init__(constraints, attribute_statistics)

    def decide(self, person: dict) -> bool:
        print("person:", json.dumps(person, separators=(",", ":")))
        return random.choice([True, False])
