from berghain.strategy_base import BaseStrategy


class Strategy(BaseStrategy):
    def __init__(self, scenario, constraints, attribute_statistics):
        super().__init__(scenario, constraints, attribute_statistics)
        self.admitted_counts = {attr: 0 for attr in self.min_required}
        self.total_admitted = 0
        self.total_rejected = 0

    def decide(self, attrs: dict[str, bool]) -> bool:
        score = self._calculate_person_score(attrs)
        threshold = self._get_dynamic_threshold()

        accept = score >= threshold

        if accept:
            self.total_admitted += 1
            for attr, value in attrs.items():
                if value and attr in self.admitted_counts:
                    self.admitted_counts[attr] += 1
        else:
            self.total_rejected += 1

        return accept

    def _calculate_person_score(self, attrs: dict[str, bool]) -> float:
        score = 0.0

        for attr, value in attrs.items():
            if value and attr in self.min_required:
                score += self._get_attribute_urgency(attr)

        score += self._get_correlation_bonus(attrs)
        return score

    def _get_attribute_urgency(self, attr: str) -> float:
        remaining_needed = self.min_required[attr] - self.admitted_counts[attr]

        if remaining_needed <= 0:
            return 0.0

        remaining_slots = 1000 - self.total_admitted

        if remaining_slots <= 0:
            return 0.0

        attr_prob = self.relative_frequencies.get(attr, 0.5)
        expected_remaining = remaining_slots * attr_prob

        if expected_remaining < 1:
            return 10.0

        return remaining_needed / expected_remaining

    def _get_correlation_bonus(self, attrs: dict[str, bool]) -> float:
        bonus = 0.0
        true_attrs = [
            attr for attr, value in attrs.items() if value and attr in self.min_required
        ]

        for attr1 in true_attrs:
            for attr2 in true_attrs:
                if attr1 != attr2 and attr1 in self.correlations:
                    correlation = self.correlations[attr1].get(attr2, 0.0)
                    if correlation > 0:
                        bonus += correlation * 0.1

        return bonus

    def _get_dynamic_threshold(self) -> float:
        base_threshold = 1.0

        if self.max_rejections == 0:
            return 0.0

        rejection_ratio = self.total_rejected / self.max_rejections
        capacity_ratio = self.total_admitted / 1000

        pressure = max(rejection_ratio, capacity_ratio)
        return base_threshold * (1 - pressure) ** 2
