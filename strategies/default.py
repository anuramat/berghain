import numpy as np
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
        n_runs: int = 1000000,
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

        if self.stats is None:
            raise Exception("no stats loaded")

        sets: list[frozenset] = self.stats[
            "sets"
        ]  # `2 ** len(attributes)` possible combinations
        counts = self.stats["counts"]
        total = self.stats["total"]

        # https://en.wikipedia.org/wiki/Categorical_distribution#Bayesian_inference_using_conjugate_prior
        alpha: float = 0
        # TODO: maybe make alpha depend on attribute
        probas = [
            ((counts[attrset] + alpha) / (total + alpha * (2 ** len(sets))))
            for attrset in sets
        ]

        runs = multinomial(
            remaining_budget + remaining_places, probas, size=n_runs
        )  # shape: n_runs, 2**k

        # WARN vibecode below

        checker = GurobiFeasibilityChecker(
            patterns=sets,
            deficits=deficits,
        )
        est, _ = estimate_feasibility_probability(
            n=remaining_budget + remaining_places,
            p=probas,
            checker=checker,
            m=remaining_places,
        )
        print(est)
        return est


import math
from typing import (
    Dict,
    FrozenSet,
    Iterable,
    List,
    Mapping,
    MutableSequence,
    Optional,
    Sequence,
    Tuple,
    Union,
)

import gurobipy as gp
import numpy as np
from gurobipy import GRB

VarName = str
Pattern = FrozenSet[VarName]
PatternsIndex = Union[Sequence[Pattern], Mapping[int, Pattern]]


def _ensure_patterns(patterns: PatternsIndex) -> List[Pattern]:
    """
    Coerce `patterns` into a 0..P-1 ordered list of frozensets.
    Accepts either:
      - a Sequence[Pattern] already ordered (e.g., list/tuple of length P), or
      - a Mapping[int, Pattern] with contiguous keys 0..P-1.
    """
    if isinstance(patterns, Mapping):
        if not patterns:
            return []
        keys = sorted(patterns.keys())
        if keys[0] != 0 or keys[-1] != len(keys) - 1 or keys != list(range(len(keys))):
            raise ValueError("Pattern mapping keys must be contiguous 0..P-1.")
        return [patterns[i] for i in range(len(keys))]
    elif isinstance(patterns, Sequence):
        return list(patterns)
    else:
        raise TypeError(
            "`patterns` must be a sequence or a mapping from int to frozenset[str]."
        )


def _wilson_interval(p_hat: float, n: int, z: float = 1.96) -> Tuple[float, float]:
    """95% Wilson score interval by default."""
    if n == 0:
        return (0.0, 1.0)
    denom = 1.0 + (z * z) / n
    center = (p_hat + (z * z) / (2 * n)) / denom
    half = z * math.sqrt((p_hat * (1 - p_hat) / n) + (z * z) / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


class GurobiFeasibilityChecker:
    """
    Reusable Gurobi model to compute f(A): the minimum number of rows needed
    to satisfy coverage lower-bounds `deficits`, given pattern counts A.

    Variables: z_j ∈ {0,1,...,A_j} for each pattern j
    Constraints: for each var i,  sum_{j: i∈pattern_j} z_j >= deficits[i]
    Objective: minimize sum_j z_j
    """

    def __init__(
        self,
        patterns: PatternsIndex,
        deficits: Dict[VarName, int],
        env: Optional[gp.Env] = None,
        time_limit_s: Optional[float] = None,
        mip_focus: Optional[int] = None,
        threads: Optional[int] = None,
        quiet: bool = True,
    ) -> None:
        self.patterns: List[Pattern] = _ensure_patterns(patterns)
        self.P: int = len(self.patterns)
        self.deficits: Dict[VarName, int] = dict(deficits)
        if any(v < 0 for v in self.deficits.values()):
            raise ValueError("All deficits must be >= 0.")

        # Build coverage index: for each variable name, which pattern indices contain it
        self.var_names: List[VarName] = sorted(self.deficits.keys())
        self.covers: Dict[VarName, List[int]] = {
            name: [j for j, pat in enumerate(self.patterns) if name in pat]
            for name in self.var_names
        }

        # Build model once; we only change UBs per trial.
        self.env = env or gp.Env(empty=True)
        if env is None:
            if quiet:
                self.env.setParam("OutputFlag", 0)
            self.env.start()

        self.model = gp.Model(env=self.env)
        if quiet:
            self.model.Params.OutputFlag = 0
        if time_limit_s is not None:
            self.model.Params.TimeLimit = float(time_limit_s)
        if mip_focus is not None:
            self.model.Params.MIPFocus = int(mip_focus)
        if threads is not None:
            self.model.Params.Threads = int(threads)

        # Decision vars: z_j ∈ [0, 0] initially; we'll set UB per trial.
        self.z: List[gp.Var] = [
            self.model.addVar(vtype=GRB.INTEGER, lb=0.0, ub=0.0, name=f"z_{j}")
            for j in range(self.P)
        ]

        # Coverage constraints
        self.constrs: Dict[VarName, gp.Constr] = {}
        for name in self.var_names:
            rhs = float(self.deficits[name])
            idxs = self.covers[name]
            self.constrs[name] = self.model.addConstr(
                gp.quicksum(self.z[j] for j in idxs) >= rhs, name=f"cover_{name}"
            )

        # Objective: minimize total selected rows
        self.model.ModelSense = GRB.MINIMIZE
        self.model.setObjective(gp.quicksum(self.z))

        self.model.update()

    def _necessary_check(self, A: np.ndarray) -> bool:
        """
        Quick necessary condition: for each variable `name`,
        sum of counts across patterns that contain `name` must be >= deficits[name].
        """
        for name in self.var_names:
            total_available = int(np.sum(A[self.covers[name]]))
            if total_available < self.deficits[name]:
                return False
        return True

    def min_rows_needed(self, A: np.ndarray) -> int:
        """
        Return f(A) or math.inf if infeasible (or proven infeasible by cuts).
        """
        if A.dtype.kind not in "iu":
            A = A.astype(int, copy=False)
        if A.shape != (self.P,):
            raise ValueError(f"A must have shape ({self.P},), got {A.shape}.")

        # Necessary infeasibility check
        if not self._necessary_check(A):
            return math.inf

        # Update UBs and solve
        for j, ub in enumerate(A.tolist()):
            self.z[j].UB = float(int(ub))
        self.model.update()
        self.model.optimize()

        status = self.model.Status
        if status in (GRB.OPTIMAL,):
            return int(round(self.model.ObjVal))
        if status == GRB.INFEASIBLE:
            return math.inf
        # If time-limited or otherwise stopped, fall back to best bound/solution
        if self.model.SolCount > 0:
            return int(round(self.model.ObjVal))
        # If no solution known, try infeasibility via IIS as last resort (optional)
        return math.inf


def estimate_feasibility_probability(
    n: int,
    p: Union[np.ndarray, Sequence[float]],
    checker: GurobiFeasibilityChecker,
    m: int,
    trials: int = 1000000,
    seed: Optional[Union[int, np.random.Generator]] = None,
) -> Tuple[float, Tuple[float, float]]:
    """
    Monte Carlo estimator for Pr[f(A) <= m], with Wilson 95% CI.

    Parameters
    ----------
    n : number of iid draws
    p : length-P probabilities matching the `checker.patterns` order
    checker : initialized GurobiFeasibilityChecker
    m : subset-size cap to test (feasible iff f(A) <= m)
    trials : number of Monte Carlo trials
    seed : RNG seed or Generator

    Returns
    -------
    (est, (lo, hi))
    """
    p_arr = np.asarray(p, dtype=float)
    if p_arr.ndim != 1 or p_arr.shape[0] != checker.P:
        raise ValueError(f"p must be length {checker.P}.")
    if not np.isclose(p_arr.sum(), 1.0):
        p_arr = p_arr / p_arr.sum()

    rng = seed if isinstance(seed, np.random.Generator) else np.random.default_rng(seed)

    successes = 0
    for _ in range(trials):
        A = rng.multinomial(n, p_arr)  # shape (P,)
        min_rows = checker.min_rows_needed(A)
        if min_rows <= m:
            successes += 1

    est = successes / trials
    ci = _wilson_interval(est, trials)
    return est, ci
