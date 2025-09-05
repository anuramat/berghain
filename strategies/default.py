from numpy.random import multinomial
from numpy.typing import NDArray

from berghain.strategy_base import BaseStrategy


class Strategy(BaseStrategy):
    def __init__(self, scenario, constraints, attribute_statistics):
        super().__init__(scenario, constraints, attribute_statistics)
        self.deficits = dict(self.min_required)  # NOTE can be negative
        self.remaining_places = 1000
        self.remaining_budget = self.max_rejections - 1

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

    def decide(self, attrs: dict[str, bool]) -> bool:
        present = [k for k, v in attrs.items() if v]
        return self._decide(present)

    def _decide(self, attrs: list[str]) -> bool:
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
        """
        Compare log-probability of "satisfiability" if we accept vs reject this person.
        """

        deficits_if_accept = dict(self.deficits)
        for k in attrs:
            deficits_if_accept[k] -= 1

        return self._satisfiability_logproba(
            deficits_if_accept,
            self.remaining_budget,
            self.remaining_places - 1,
        ) - self._satisfiability_logproba(
            self.deficits, self.remaining_budget - 1, self.remaining_places
        )

    def _satisfiability_logproba(
        self,
        deficits: dict[str, int],
        remaining_budget: int,
        remaining_places: int,
        n_runs: int = 1024,
    ) -> float:
        """
        Informally -- satisfiability means that we can win if we make all the right choices.

        More formally: probability that if we sample
        n=remaining_budget+remaining_places people, out of those n people there
        is a subset of m=remaining_budget people, such that choosing them
        satisfies all attribute constraints

        To esimate that probability, we will use Monte-Carlo and the esimated
        joint probability distribution:

        n_runs times we sample `remaining_budget+remainint_places` persons, and
        check if there is a `remaining_places` subset that satisfies attribute
        constraints

        NOTE we could go a few steps exactly, and then do monte-carlo? would that decrese the estimate variance?
        """
        runs = self._get_mc_runs(n_runs, remaining_budget, remaining_places)
        good = [self._satisfiable(run) for run in runs]
        return len(good) / n_runs

    def _satisfiable(self, run) -> bool: ...

    def _get_mc_runs(
        self, n_runs: int, remaining_budget: int, remaining_places: int
    ) -> NDArray:
        if self.stats is None:
            raise Exception("no stats loaded")

        sets = self.stats["sets"]  # `2 ** len(attributes)` possible combinations
        counts = self.stats["counts"]
        total = self.stats["total"]

        # https://en.wikipedia.org/wiki/Categorical_distribution#Bayesian_inference_using_conjugate_prior
        alpha: float = 0
        # TODO: maybe make alpha depend on attribute
        probas = [
            ((counts[attrset] + alpha) / (total + alpha * (2 ** len(sets))))
            for attrset in sets
        ]

        return multinomial(
            remaining_budget + remaining_places, probas, size=n_runs
        )  # shape: n_runs, 2**k
