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
        n_runs: int = 100000,
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

        feas = monte_carlo_feasibility(
            runs, sets, deficits, remaining_places
        )  # TODO refactor below
        cnt = 0
        for i in feas[0]:
            if i:
                cnt += 1

        print(cnt)

        return cnt / total

    def _satisfiable(self, run) -> bool:
        raise NotImplemented


import numpy as np
from ortools.sat.python import cp_model


# ---------- compile once (from your schema) ----------
def build_cover_index(sets, deficits):
    """
    sets: list[frozenset[str]] of length P (P=64) — pattern j contains these variable names
    deficits: dict[str,int] — required counts per variable (c_i)

    returns:
      cover_ix_by_var: dict[str, np.ndarray[int]] of pattern indices covering that var
      all_vars: sorted tuple of var names (for sanity)
    """
    P = len(sets)
    cover_ix_by_var = {v: [] for v in deficits.keys()}
    for j, S in enumerate(sets):
        for v in S:
            if v in cover_ix_by_var:  # ignore vars not constrained
                cover_ix_by_var[v].append(j)
    # freeze as numpy arrays (faster in loops)
    cover_ix_by_var = {
        v: np.array(ix, dtype=np.int32) for v, ix in cover_ix_by_var.items()
    }
    return cover_ix_by_var, tuple(sorted(deficits.keys()))


# ---------- per-trial solve ----------
def solve_trial_cpsat(
    A_vec, cover_ix_by_var, deficits, m=None, check_only=True, time_limit_s=0.2
):
    """
    A_vec: np.ndarray shape (P,) counts for this run (P must match len(sets))
    cover_ix_by_var/deficits: from above
    m: max rows allowed (required if check_only=True)
    check_only:
       - True  -> SAT check with constraint sum(z) <= m (fast feasibility test)
       - False -> minimize sum(z) and return min rows
    returns: (is_feasible, min_rows_or_None)
    """
    # quick impossibility pruning: if a var cannot be covered even using all rows of its covering patterns
    for v, req in deficits.items():
        if req <= 0:
            continue
        ix = cover_ix_by_var.get(v, None)
        if ix is None or ix.size == 0:
            return (False, None)
        if int(A_vec[ix].sum()) < int(req):
            return (False, None)

    model = cp_model.CpModel()
    P = int(A_vec.shape[0])

    # decision vars: 0 <= z_j <= A_vec[j]
    z = [model.NewIntVar(0, int(A_vec[j]), f"z_{j}") for j in range(P)]

    # coverage constraints: for each constrained variable v, sum_{patterns covering v} z_j >= c_v
    for v, req in deficits.items():
        if req <= 0:
            continue
        ix = cover_ix_by_var[v]
        # guard: ix might be empty handled above
        model.Add(sum(z[j] for j in ix.tolist()) >= int(req))

    if check_only:
        assert m is not None, "m is required for check_only=True"
        model.Add(sum(z) <= int(m))
        # satisfaction only (no objective)
    else:
        model.Minimize(sum(z))

    solver = cp_model.CpSolver()
    if time_limit_s is not None:
        solver.parameters.max_time_in_seconds = float(time_limit_s)
    # Use multiple workers if available
    solver.parameters.num_search_workers = 8

    res = solver.Solve(model)
    if res in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        if check_only:
            return (True, None)
        else:
            return (True, int(round(solver.ObjectiveValue())))
    else:
        # UNSAT or time-out with no feasible solution found
        if check_only:
            return (False, None)
        else:
            return (False, None)


# ---------- batch wrapper over your counts matrix ----------
def monte_carlo_feasibility(
    counts_matrix, sets, deficits, m, time_limit_s=0.2, check_only=True
):
    """
    counts_matrix: np.ndarray shape (n_runs, P=64)
    sets: list[frozenset[str]] length P
    deficits: dict[str,int]
    m: subset size limit
    returns:
      feasible_flags: np.ndarray[bool] length n_runs
      mins_or_none: np.ndarray[int] (min rows if check_only=False, else all -1)
    """
    cover_ix_by_var, _ = build_cover_index(sets, deficits)
    n_runs, P = counts_matrix.shape
    feasible = np.zeros(n_runs, dtype=bool)
    mins = np.full(n_runs, -1, dtype=np.int32)

    for t in range(n_runs):
        A_vec = counts_matrix[t]
        ok, min_rows = solve_trial_cpsat(
            A_vec=A_vec,
            cover_ix_by_var=cover_ix_by_var,
            deficits=deficits,
            m=m,
            check_only=check_only,
            time_limit_s=time_limit_s,
        )
        feasible[t] = ok
        if (not check_only) and (min_rows is not None):
            mins[t] = min_rows
    return feasible, mins
