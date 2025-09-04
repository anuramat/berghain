from scipy.stats import binom

from berghain.strategy_base import BaseStrategy


class Strategy(BaseStrategy):
    def __init__(self, scenario, constraints, attribute_statistics):
        super().__init__(scenario, constraints, attribute_statistics)
        self.deficits = dict(self.min_required)
        self.remaining_places = 1000
        self.remaining_budget = self.max_rejections - 1

    def decide(self, attrs: dict[str, bool]) -> bool:
        present = [k for k, v in attrs.items() if v]
        return self._decide(present)

    def _decide(self, attrs: list[str]) -> bool:
        self.log()

        unmet = [k for k, v in self.deficits.items() if v > 0]
        if not unmet:
            return self._accept(attrs, reason="we just need more people")

        if not any(k in unmet for k in attrs):
            return self._reject(reason="doesnt decrease deficits")

        if len(attrs) == len(self.deficits):
            return self._accept(attrs, reason="all attributes")

        if self._satisfiability_logproba_diff() < 0:
            return self._reject(reason="proba")
        return self._accept(attrs, reason="proba")

    def _satisfiability_logproba_diff(self) -> float:
        # TODO
        deficits_if_accept = ...
        deficits_if_reject = ...
        return self._satisfiability_logproba(
            deficits_if_accept
        ) - self._satisfiability_logproba(deficits_if_reject)

    def _satisfiability_logproba(self, deficits) -> float:
        """
        Probability that among next `remaining_budget + remaining_places` people
        there exists a subset of size `remaining_places` that clears all deficits.
        """
        # logprobas = sum(binom.logsf(deficit - 1, remaining, proba))
        return 0.0

    def _joint(self):
        pass

    def _reject(self, reason: str = "") -> bool:
        if reason:
            print(reason)
        self.remaining_budget -= 1
        if self.remaining_budget == 0:
            print("--- rejection budget exceeded ---")
        return False

    def _accept(self, attrs: list[str], reason: str = "") -> bool:
        if reason:
            print(reason)
        self.remaining_places -= 1
        for k in attrs:
            if k in self.deficits and self.deficits[k] > 0:
                self.deficits[k] -= 1
        return True

    def log(self):
        pass  # TODO move unconditional logging here
