from berghain.strategy_base import BaseStrategy


class Strategy(BaseStrategy):
    def __init__(self, scenario, constraints, attribute_statistics):
        super().__init__(scenario, constraints, attribute_statistics)
        self.deficits = dict(self.min_required)
        self.accepted_count = 0

    def decide(self, attrs: dict[str, bool]) -> bool:
        if self.accepted_count >= 1000:
            return False

        person_attributes = [attr for attr, value in attrs.items() if value]

        contributes_to_deficit = any(
            attr in person_attributes and self.deficits.get(attr, 0) > 0
            for attr in person_attributes
        )

        has_unmet_quotas = any(deficit > 0 for deficit in self.deficits.values())

        if not contributes_to_deficit and has_unmet_quotas:
            return False

        self.accepted_count += 1
        for attr in person_attributes:
            if attr in self.deficits and self.deficits[attr] > 0:
                self.deficits[attr] -= 1

        return True
