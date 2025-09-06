from functools import partial
from multiprocessing import Pool
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
        self.remaining_accepts = 1000
        self.remaining_rejects = self.max_rejections - 1

        if self.stats is None:
            raise Exception("no stats loaded")
        self.proba = self.stats["proba"]

    def _reject(self, reason: str = "") -> bool:
        if reason:
            print(reason)
        self.remaining_rejects -= 1
        if self.remaining_rejects == 0:
            print("--- rejection budget exceeded ---")
        return False

    def _accept(self, attrs: list[str], reason: str = "") -> bool:
        if reason:
            print(reason)
        self.remaining_accepts -= 1
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
            self.remaining_rejects,
            self.remaining_accepts - 1,
        ) - self._satisfiability_proba(
            self.deficits, self.remaining_rejects - 1, self.remaining_accepts
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

    @staticmethod
    def _solve_single_run(args):
        """Solve a single CP problem for one run. Used by multiprocessing."""
        run, cover_ix_by_var, deficits, remaining_accepts = args

        # Early impossibility detection
        for attr, deficit in deficits.items():
            if deficit <= 0:
                continue
            ix = cover_ix_by_var.get(attr)
            if ix is None or ix.size == 0:
                return False
            if int(run[ix].sum()) < deficit:
                return False

        model = cp_model.CpModel()

        # Decision variables
        x = []
        for i in range(len(run)):
            x.append(model.NewIntVar(0, int(run[i]), f"x_{i}"))

        # Total constraint
        model.Add(sum(x) == remaining_accepts)

        # Deficit constraints
        for attr, deficit in deficits.items():
            if deficit > 0:
                ix = cover_ix_by_var[attr]
                model.Add(sum(x[j] for j in ix.tolist()) >= deficit)

        # Solve
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 0.2
        solver.parameters.num_search_workers = 1  # Single worker per subprocess

        status = solver.Solve(model)
        return status in (cp_model.FEASIBLE, cp_model.OPTIMAL)

    def _satisfiability_proba(
        self,
        deficits: dict[str, int],
        remaining_rejects: int,
        remaining_accepts: int,
        n_runs: int = 1000000,
    ) -> float:
        """
        Informally -- satisfiability means that we can win if we make all the right choices.

        More formally: probability that if we sample
        n=remaining_rejects+remaining_accepts people, out of those n people there
        is a subset of m=remaining_rejects people, such that choosing them
        satisfies all attribute constraints (deficits)

        To esimate that probability, we will use Monte-Carlo and the esimated
        joint probability distribution:

        n_runs times we sample `remaining_rejects+remaining_accepts` persons, and
        check if there is a `remaining_accepts` subset that satisfies attribute
        constraints
        """

        if remaining_accepts == 0 or remaining_rejects == 0:
            raise NotImplementedError(
                "Edge case: remaining_accepts or remaining_rejects is 0"
            )

        gen_start = time()
        runs = multinomial(
            remaining_rejects + remaining_accepts, self.proba, size=n_runs
        )
        print(f"generated {n_runs} runs in {time() - gen_start:.2f}s")

        # Pre-compute coverage indices
        bits_to_set = self.stats["bits_to_set"]
        cover_ix_by_var = self._build_coverage_index(bits_to_set, deficits)

        # Vectorized early detection - check all runs at once
        feasible_mask = np.ones(n_runs, dtype=bool)
        for attr, deficit in deficits.items():
            if deficit <= 0:
                continue
            ix = cover_ix_by_var.get(attr)
            if ix is None or ix.size == 0:
                return 0.0  # No way to satisfy this constraint
            # Check all runs simultaneously
            attr_sums = runs[:, ix].sum(axis=1)
            feasible_mask &= attr_sums >= deficit

        # Get indices of potentially feasible runs
        feasible_indices = np.where(feasible_mask)[0]
        print(
            f"Pre-filtered to {len(feasible_indices)}/{n_runs} potentially feasible runs"
        )

        if len(feasible_indices) == 0:
            return 0.0

        # Prepare arguments for multiprocessing
        args_list = [
            (runs[i], cover_ix_by_var, deficits, remaining_accepts)
            for i in feasible_indices
        ]

        # Process in parallel with early stopping
        n_procs = 16
        batch_size = len(args_list) // n_procs
        n_feasible = 0
        n_processed = 0

        mc_start = time()

        with Pool(processes=n_procs) as pool:
            for batch_start in range(0, len(args_list), batch_size):
                batch_end = min(batch_start + batch_size, len(args_list))
                batch_args = args_list[batch_start:batch_end]

                # Process batch in parallel
                results = pool.map(self._solve_single_run, batch_args)
                n_feasible += sum(results)
                n_processed += len(results)

        print(f"solved {len(feasible_indices)} CP problems in {time() - mc_start:.2f}s")
        print(n_feasible)

        # Return probability accounting for pre-filtering
        return (n_feasible / len(feasible_indices)) * (len(feasible_indices) / n_runs)
