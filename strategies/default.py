from time import time

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

        if self._satisfiability_proba_diff(attrs) < 0:
            return self._reject(reason="proba")
        return self._accept(attrs, reason="proba")

    def _satisfiability_proba_diff(self, attrs: list[str]) -> float:
        """
        Compare probability of "satisfiability" if we accept vs reject this person.
        """

        deficits_if_accept = dict(self.deficits)
        for k in attrs:
            deficits_if_accept[k] -= 1

        diff = self._satisfiability_proba(
            deficits_if_accept,
            self.remaining_budget,
            self.remaining_places - 1,
        ) - self._satisfiability_proba(
            self.deficits, self.remaining_budget - 1, self.remaining_places
        )
        print("proba diff:", diff)
        return diff

    def _build_coverage_index(self, bits_to_set, deficits):
        """Pre-compute which patterns cover which variables."""
        cover_ix_by_var = {v: [] for v in deficits.keys()}
        for j, pattern in enumerate(bits_to_set):
            for v in pattern:
                if v in cover_ix_by_var:
                    cover_ix_by_var[v].append(j)
        # Convert to numpy arrays for faster access
        cover_ix_by_var = {
            v: np.array(ix, dtype=np.int32) for v, ix in cover_ix_by_var.items()
        }
        return cover_ix_by_var

    def _satisfiability_proba(
        self,
        deficits: dict[str, int],
        remaining_budget: int,
        remaining_places: int,
        n_runs: int = 100000,
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

        if remaining_places == 0 or remaining_budget == 0:
            raise NotImplementedError(
                "Edge case: remaining_places or remaining_budget is 0"
            )

        gen_start = time()
        runs = multinomial(remaining_budget + remaining_places, self.proba, size=n_runs)
        print("generted runs in", time() - gen_start)

        # Pre-compute coverage indices once for all runs
        bits_to_set = self.stats["bits_to_set"]
        cover_ix_by_var = self._build_coverage_index(bits_to_set, deficits)

        n_feasible = 0
        mc_start = time()

        for run in runs:
            # Early impossibility detection
            possible = True
            for attr, deficit in deficits.items():
                if deficit <= 0:
                    continue
                ix = cover_ix_by_var.get(attr)
                if ix is None or ix.size == 0:
                    possible = False
                    break
                # Check if we have enough people with this attribute
                if int(run[ix].sum()) < deficit:
                    possible = False
                    break

            if not possible:
                continue

            model = cp_model.CpModel()

            # Decision variables: x[i] = number of people with attribute combination i to select
            x = []
            for i in range(len(run)):
                x.append(model.NewIntVar(0, int(run[i]), f"x_{i}"))

            # Constraint: select exactly remaining_places people
            model.Add(sum(x) == remaining_places)

            # Deficit constraints using pre-computed indices
            for attr, deficit in deficits.items():
                if deficit > 0:
                    ix = cover_ix_by_var[attr]
                    # Use pre-computed indices directly
                    model.Add(sum(x[j] for j in ix.tolist()) >= deficit)

            # Solve with optimized parameters
            solver = cp_model.CpSolver()
            solver.parameters.max_time_in_seconds = 0.2
            solver.parameters.num_search_workers = 8

            status = solver.Solve(model)

            if status == cp_model.FEASIBLE or status == cp_model.OPTIMAL:
                n_feasible += 1

        print("solved in", time() - mc_start)

        return n_feasible / n_runs
