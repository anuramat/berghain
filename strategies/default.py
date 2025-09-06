import numpy as np
from numba import njit
from numpy.random import multinomial
from numpy.typing import NDArray
from ortools.sat.python import cp_model

from berghain.strategy_base import BaseStrategy


class Strategy(BaseStrategy):
    def __init__(self, scenario, constraints, attribute_statistics):
        super().__init__(scenario, constraints, attribute_statistics)
        self.deficits = dict(self.min_required)  # NOTE can be negative
        self.remaining_places = 1000
        self.remaining_budget = self.max_rejections - 1

        if self.stats is None:
            raise Exception("no stats loaded")
        self.proba = self.stats["proba"]

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
        # TODO we're not gonna use logproba, so rename everything and edit comments
        """
        Compare log-probability of "satisfiability" if we accept vs reject this person.
        """

        deficits_if_accept = dict(self.deficits)
        for k in attrs:
            deficits_if_accept[k] -= 1

        diff = self._satisfiability_logproba(
            deficits_if_accept,
            self.remaining_budget,
            self.remaining_places - 1,
        ) - self._satisfiability_logproba(
            self.deficits, self.remaining_budget - 1, self.remaining_places
        )
        print("proba diff:", diff)
        return diff

    def _satisfiability_logproba(
        self,
        deficits: dict[str, int],
        remaining_budget: int,
        remaining_places: int,
        n_runs: int = 10000,
    ) -> float:
        """
        Informally -- satisfiability means that we can win if we make all the right choices.

        More formally: probability that if we sample
        n=remaining_budget+remaining_places people, out of those n people there
        is a subset of m=remaining_budget people, such that choosing them
        satisfies all attribute constraints (deficits)

        To esimate that probability, we will use Monte-Carlo and the esimated
        joint probability distribution:

        n_runs times we sample `remaining_budget+remaining_places` persons, and
        check if there is a `remaining_places` subset that satisfies attribute
        constraints
        """

        runs = multinomial(remaining_budget + remaining_places, self.proba, size=n_runs)

        # TODO use a cpsolver from ortools to calculate how many runs are feasible, then return `n_feasible/n_runs`

        raise NotImplementedError
