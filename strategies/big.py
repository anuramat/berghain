from __future__ import annotations

"""
Max-probability quota strategy for arbitrary (<=6) binary attributes.

Implements an optimal finite-horizon DP over (R, u, d) where:
  - R = remaining arrivals you are allowed to see (R = T - t, with T = N + B)
  - u = remaining accepts needed to reach N (u = N - a)
  - d = vector of remaining minima (per constrained attribute), clipped at >= 0

The DP value function f(R,u,d) returns the maximal success probability
(from this state, *before* seeing the next arrival), with randomness coming
from the arrival distribution over constraint-contribution patterns.

At decision time, we observe the concrete arriving person (attrs dict) and
compare the two Q-values conditioned on this person:
   - Accept:  f(R-1, u-1, d - w_obs)
   - Reject:  f(R-1, u,   d)
Pick the action with the higher continuation value, subject to feasibility
(u>0 for accept, u<R for reject). Also enforce structural must-accept /
must-reject rules (accept-all when R==u; tight-constraint rule when some
constraint has d_l == u).

The arrival distribution over all 2^m attribute combinations is modeled by
a binary maximum-entropy (log-linear / Ising with 0/1 coding) model with
singleton and pairwise features. We fit parameters by minimizing the convex
objective logZ(w) - w^T m_target using Adam; with m<=6 we can enumerate 2^m
states exactly for Z and expectations.

If pairwise correlations are not provided, the model reduces to independent
Bernoulli features (maximum-entropy with singleton constraints only).
"""

import math
from dataclasses import dataclass
from itertools import combinations, product
from typing import Dict, List, Tuple

from berghain.strategy_base import BaseStrategy

# ----------------------------- Utilities ---------------------------------


def _clip01(x: float, eps: float = 1e-6) -> float:
    return min(max(x, eps), 1.0 - eps)


def _enumerate_states(m: int) -> List[Tuple[int, ...]]:
    """All binary states as tuples of 0/1 of length m."""
    return [tuple(map(int, s)) for s in product([0, 1], repeat=m)]


def _build_feature_map(m: int) -> Tuple[List[Tuple[int]], List[Tuple[int, int]]]:
    """Return lists of singleton indices and pair indices (i<j)."""
    singles = [(i,) for i in range(m)]
    pairs = [(i, j) for i, j in combinations(range(m), 2)]
    return singles, pairs


def _state_features(
    x: Tuple[int, ...], singles: List[Tuple[int]], pairs: List[Tuple[int, int]]
) -> Tuple[List[float], List[float]]:
    """Compute singleton and pairwise features for state x in {0,1}^m."""
    f1 = [float(x[i]) for (i,) in singles]
    f2 = [float(x[i] * x[j]) for (i, j) in pairs]
    return f1, f2


# -------------------- Max-entropy (Ising 0/1) fitting ---------------------


def fit_maxent_binary_joint(
    marginals: List[float],
    target_corr: List[List[float]] | None = None,
    max_iter: int = 4000,
    tol: float = 1e-7,
    lr: float = 0.2,
) -> Dict[Tuple[int, ...], float]:
    """
    Fit a 0/1 log-linear model p(x) ∝ exp(θ^T x + x^T J x) to match
    E[X_i] = marginals[i] and (if target_corr provided) Corr(X_i,X_j) = target_corr[i][j].

    With m ≤ 6 states, we enumerate exactly and optimize the convex dual
    f(θ,J) = log Z(θ,J) - <θ,J; targets>, with gradient = model_moments - targets.

    If correlations are None, we set pairwise targets to E[X_i]E[X_j] (i.e., zero corr).

    Returns: dict mapping state tuple (0/1)^m -> probability.
    """
    m = len(marginals)
    mu = [_clip01(p) for p in marginals]

    singles, pairs = _build_feature_map(m)

    # Build target pairwise expectations E[X_i X_j] from correlations if given
    E2_target = {}
    for i, j in pairs:
        if (
            target_corr
            and target_corr[i]
            and (j < len(target_corr[i]))
            and (target_corr[i][j] is not None)
        ):
            rho = float(target_corr[i][j])
            rho = max(min(rho, 0.9999), -0.9999)
            s = math.sqrt(mu[i] * (1 - mu[i]) * mu[j] * (1 - mu[j]))
            eij = mu[i] * mu[j] + rho * s
        else:
            eij = mu[i] * mu[j]
        # Clip to feasible range
        lo = max(0.0, mu[i] + mu[j] - 1.0)
        hi = min(mu[i], mu[j])
        E2_target[(i, j)] = min(max(eij, lo + 1e-8), hi - 1e-8)

    # Targets vector: first singles (means), then pairs (E[XiXj])
    target_vec = [mu[i] for (i,) in singles] + [E2_target[(i, j)] for (i, j) in pairs]

    # Parameter vector w = [theta_i..., J_ij...]
    w = [0.0 for _ in target_vec]
    m_states = _enumerate_states(m)

    # Adam optimizer state
    beta1, beta2, eps = 0.9, 0.999, 1e-8
    m_adam = [0.0 for _ in w]
    v_adam = [0.0 for _ in w]

    def moments_and_logZ(params: List[float]) -> Tuple[List[float], float]:
        """Compute model moments E[f] and logZ for given params."""
        # Unpack
        thetas = params[: len(singles)]
        J = params[len(singles) :]
        # energies and weights
        feats_cache = []
        log_weights = []
        for x in m_states:
            f1, f2 = _state_features(x, singles, pairs)
            feats_cache.append((f1, f2))
            energy = sum(t * v for t, v in zip(thetas, f1)) + sum(
                jv * v for jv, v in zip(J, f2)
            )
            log_weights.append(energy)
        # log-sum-exp
        mlog = max(log_weights)
        weights = [math.exp(lw - mlog) for lw in log_weights]
        Z = sum(weights)
        probs = [w_ / Z for w_ in weights]
        # moments
        E1 = [0.0] * len(singles)
        E2 = [0.0] * len(pairs)
        for p, (f1, f2) in zip(probs, feats_cache):
            for k in range(len(E1)):
                E1[k] += p * f1[k]
            for k in range(len(E2)):
                E2[k] += p * f2[k]
        logZ = mlog + math.log(Z)
        return E1 + E2, logZ

    prev_obj = float("inf")
    for it in range(1, max_iter + 1):
        model_mom, logZ = moments_and_logZ(w)
        # convex dual objective
        obj = logZ - sum(wk * tv for wk, tv in zip(w, target_vec))
        # gradient = model - target
        grad = [mm - tv for mm, tv in zip(model_mom, target_vec)]
        # convergence check
        gnorm = math.sqrt(sum(g * g for g in grad))
        if gnorm < tol:
            break
        # Adam update
        for k in range(len(w)):
            m_adam[k] = beta1 * m_adam[k] + (1 - beta1) * grad[k]
            v_adam[k] = beta2 * v_adam[k] + (1 - beta2) * (grad[k] ** 2)
            mhat = m_adam[k] / (1 - beta1**it)
            vhat = v_adam[k] / (1 - beta2**it)
            w[k] -= lr * mhat / (math.sqrt(vhat) + eps)
        # small damping if objective increases for many steps
        if obj > prev_obj and it % 200 == 0:
            lr *= 0.5
        prev_obj = obj

    # Final distribution
    # Reuse moments routine to get probabilities
    thetas = w[: len(singles)]
    J = w[len(singles) :]
    log_weights = []
    for x in m_states:
        f1, f2 = _state_features(x, singles, pairs)
        energy = sum(t * v for t, v in zip(thetas, f1)) + sum(
            jv * v for jv, v in zip(J, f2)
        )
        log_weights.append(energy)
    mlog = max(log_weights)
    weights = [math.exp(lw - mlog) for lw in log_weights]
    Z = sum(weights)
    probs = [w_ / Z for w_ in weights]
    return {x: p for x, p in zip(m_states, probs)}


# ----------------------------- Strategy -----------------------------------


@dataclass
class _DPEnv:
    N: int
    B: int
    patterns: List[Tuple[Tuple[int, ...], float]]  # list of (gamma, prob)


class Strategy(BaseStrategy):
    """Optimal DP strategy with max-entropy arrival model (m ≤ 6).

    - Uses the joint distribution from `fit_maxent_binary_joint` aggregated to
      constraint-contribution patterns over the attributes with minima.
    - Memoized DP over (R, u, d) with structural shortcuts.
    - `decide(attrs)` returns True to accept, False to reject, and updates
      internal counters.
    """

    N: int = 1000  # venue size

    def __init__(
        self, scenario: int, constraints: list[dict], attribute_statistics: dict
    ):
        super().__init__(scenario, constraints, attribute_statistics)

        # Attribute universe (keep stable order)
        attr_names = sorted(
            {*self.relative_frequencies.keys(), *self.min_required.keys()}
        )
        self.attr_names: List[str] = attr_names
        self.attr_index: Dict[str, int] = {a: i for i, a in enumerate(attr_names)}
        m = len(attr_names)
        if m == 0:
            raise ValueError("No attributes provided.")
        if m > 6:
            raise ValueError("This strategy supports up to 6 binary attributes.")

        # Build marginals in the same order
        mu = [_clip01(float(self.relative_frequencies.get(a, 0.5))) for a in attr_names]

        # Build correlation matrix (upper triangle used), default 0
        corr = [[0.0 for _ in range(m)] for _ in range(m)]
        for i, ai in enumerate(attr_names):
            for j, aj in enumerate(attr_names):
                if j <= i:
                    continue
                rho = None
                if ai in self.correlations and aj in self.correlations[ai]:
                    rho = float(self.correlations[ai][aj])
                elif aj in self.correlations and ai in self.correlations[aj]:
                    rho = float(self.correlations[aj][ai])
                corr[i][j] = rho if rho is not None else 0.0

        # Fit max-entropy joint
        joint = fit_maxent_binary_joint(mu, corr)

        # Constraints (minima) order and vectorization helpers
        self.cons_attrs: List[str] = list(self.min_required.keys())
        self.cons_index: Dict[str, int] = {c: i for i, c in enumerate(self.cons_attrs)}
        self.L: int = len(self.cons_attrs)

        # Aggregate probabilities by contribution pattern over constrained attributes
        # pattern gamma in {0,1}^L where gamma[l] = 1 iff state has cons_attr_l == True
        pattern_prob: Dict[Tuple[int, ...], float] = {}
        for state, p in joint.items():
            gamma = tuple(int(state[self.attr_index[c]]) for c in self.cons_attrs)
            pattern_prob[gamma] = pattern_prob.get(gamma, 0.0) + float(p)
        # Normalize (safety)
        s = sum(pattern_prob.values()) or 1.0
        for k in list(pattern_prob.keys()):
            pattern_prob[k] /= s
        self.patterns: List[Tuple[Tuple[int, ...], float]] = list(pattern_prob.items())

        # DP env and cache
        self.T: int = self.N + self.max_rejections
        self._env = _DPEnv(N=self.N, B=self.max_rejections, patterns=self.patterns)
        self._cache: Dict[Tuple[int, int, Tuple[int, ...]], float] = {}

        # Running counters
        self.t = 0  # processed arrivals
        self.a = 0  # accepted
        self.r = 0  # rejected
        self.accepted_per_attr: Dict[str, int] = {a: 0 for a in attr_names}

    # ---------------------------- DP core ---------------------------------

    def _canonical(
        self, R: int, u: int, d: Tuple[int, ...]
    ) -> Tuple[int, int, Tuple[int, ...]]:
        if u < 0 or R < 0:
            return R, u, d
        # Clamp deficits to [0, u] (if any d>u -> still representable but will die quickly)
        d2 = tuple(0 if x < 0 else (u if x > u else x) for x in d)
        return R, u, d2

    def _f(self, R: int, u: int, d: Tuple[int, ...]) -> float:
        """Value function: max success probability from state (R,u,d),
        before seeing the next arrival.
        """
        R, u, d = self._canonical(R, u, d)
        key = (R, u, d)
        if key in self._cache:
            return self._cache[key]

        # Immediate impossibilities
        if u < 0 or R < 0 or u > R:
            return 0.0
        if R == 0:
            val = 1.0 if (u == 0 and all(x == 0 for x in d)) else 0.0
            self._cache[key] = val
            return val

        # If no constraints active (L==0), policy reduces to meeting u within R
        if self.L == 0:
            # Succeed iff you can accept u within R (always true here); probability 1
            val = 1.0
            self._cache[key] = val
            return val

        # Compute reject branch value once (valid only if rejection slack exists: u < R)
        reject_val_next = self._f(R - 1, u, d) if u < R else 0.0

        # Expectation over arrival patterns: choose per-pattern best action
        best = 0.0
        for gamma, pg in self._env.patterns:
            if pg <= 0.0:
                continue
            # Accept branch only if we still need accepts
            if u > 0:
                d_new = tuple(max(0, di - gi) for di, gi in zip(d, gamma))
                accept_val = self._f(R - 1, u - 1, d_new)
            else:
                accept_val = 0.0
            # Choose better action for this realized pattern
            q = accept_val if accept_val >= reject_val_next else reject_val_next
            best += pg * q

        self._cache[key] = best
        return best

    # -------------------------- Policy rules ------------------------------

    def _deficits(self) -> Tuple[int, ...]:
        return tuple(
            max(0, int(self.min_required[c]) - int(self.accepted_per_attr.get(c, 0)))
            for c in self.cons_attrs
        )

    def _pattern_of(self, attrs: Dict[str, bool]) -> Tuple[int, ...]:
        return tuple(1 if attrs.get(c, False) else 0 for c in self.cons_attrs)

    # ----------------------------- API ------------------------------------

    def decide(self, attrs: Dict[str, bool]) -> bool:  # type: ignore[override]
        """Return True to ACCEPT, False to REJECT, and update internal state.
        Implements the DP-optimal decision using continuation values and
        structural shortcuts. Assumes each call corresponds to one arrival.
        """
        # Compute current state
        R = (self.N + self.max_rejections) - self.t
        u = self.N - self.a
        d = self._deficits()

        # If venue already full, reject by default (shouldn't happen in engine)
        if u <= 0:
            self.t += 1
            self.r += 1
            return False

        # If no rejection slack left -> accept all
        if R == u:
            decision = True
        else:
            # Tight-constraint rule: if any deficit equals u, every remaining accept must satisfy that attribute
            tight_idxs = [k for k, x in enumerate(d) if x == u]
            if tight_idxs:
                # Accept only if this arrival satisfies ALL tight attributes
                gamma_obs = self._pattern_of(attrs)
                decision = all(gamma_obs[k] == 1 for k in tight_idxs)
            else:
                # DP comparison conditioned on the observed arrival
                gamma_obs = self._pattern_of(attrs)
                accept_val = self._f(
                    R - 1, u - 1, tuple(max(0, di - gi) for di, gi in zip(d, gamma_obs))
                )
                reject_val = self._f(R - 1, u, d)
                decision = accept_val >= reject_val

        # Apply decision and update counters
        self.t += 1
        if decision:
            self.a += 1
            for a_name, truth in attrs.items():
                if truth:
                    self.accepted_per_attr[a_name] = (
                        self.accepted_per_attr.get(a_name, 0) + 1
                    )
        else:
            self.r += 1
        return decision
