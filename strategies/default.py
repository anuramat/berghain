from berghain.strategy_base import BaseStrategy


class Strategy(BaseStrategy):
    def __init__(self, scenario, constraints, attribute_statistics):
        super().__init__(scenario, constraints, attribute_statistics)
        self.deficits = dict(self.min_required)
        self.accepted_count = 0
        self.remaining_budget = self.max_rejections

    def decide(self, attrs: dict[str, bool]) -> bool:
        person_attributes: list[str] = [k for k, v in attrs.items() if v]
        return self._decide(person_attributes)

    def _decide(self, attrs: list[str]) -> bool:
        self.log()

        unmet_quotas: list[str] = [k for k, v in self.deficits.items() if v > 0]
        if not unmet_quotas:
            return self._accept(attrs)

        contributes_to_deficit = any(k in unmet_quotas for k in attrs)
        if not contributes_to_deficit:
            return self._reject()

        # "all or nothing" with known lower bound
        # XXX might want to relax, since we don't need to be top1 in isolated scenarios, only in combined score
        if self.remaining_budget == 0:
            return self._accept(attrs)

        # XXX main logic starts here
        return self._accept(attrs)

    def _reject(self) -> bool:
        self.remaining_budget -= 1
        return False

    def _accept(self, attrs) -> bool:
        self.accepted_count += 1
        for k, v in attrs.items():
            if v and k in self.deficits and self.deficits[k] > 0:
                self.deficits[k] -= 1
        return True

    def log(self):
        pass  # TODO print self...
