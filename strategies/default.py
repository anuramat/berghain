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

        if self._satisfiability_logproba_diff(attrs) < 0:
            return self._reject(reason="proba")
        return self._accept(attrs, reason="proba")

    def _satisfiability_logproba_diff(self, attrs: list[str]) -> float:
        """Compare win log-probability if we accept vs reject this person."""
        deficits_if_reject = dict(self.deficits)
        deficits_if_accept = dict(deficits_if_reject)
        for k in attrs:
            if k in deficits_if_accept and deficits_if_accept[k] > 0:
                deficits_if_accept[k] -= 1

        remaining_if_accept = (self.remaining_budget) + (self.remaining_places - 1)
        remaining_if_reject = (self.remaining_budget - 1) + (self.remaining_places)

        return self._satisfiability_logproba(
            deficits_if_accept, remaining_if_accept
        ) - self._satisfiability_logproba(deficits_if_reject, remaining_if_reject)

    def _satisfiability_logproba(
        self, deficits: dict[str, int], remaining: int
    ) -> float:
        """Approximate log P(all deficits satisfiable) with independent binomials."""
        if remaining <= 0:
            return float("-inf") if any(v > 0 for v in deficits.values()) else 0.0
        logp = 0.0
        for attr, need in deficits.items():
            if need <= 0:
                continue
            p = float(self.relative_frequencies.get(attr, 0.0))
            if p <= 0.0:
                return float("-inf")
            logp += float(binom.logsf(need - 1, remaining, p))
        return logp

    def _joint(self):
        """Return joint distribution estimate as {frozenset(attrs): prob}."""
        je = self.joint_estimate
        if not je:
            return {}
        total = max(1, int(je.get("total", 1)))
        return {k: v / total for k, v in je.get("joint_counts", {}).items()}

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
            self.deficits[k] -= 1
        return True

    def log(self):
        """Hook for unconditional logging (no-op)."""
        return None
