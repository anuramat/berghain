from __future__ import annotations

from typing import Dict

from berghain.strategy_base import BaseStrategy


class Strategy(BaseStrategy):
    """
    Implements the single-run optimal rule for two binary attributes:
      - Always keep a feasible completion possible.
      - Admit iff admitting keeps feasibility; otherwise reject.
      - Once all deficits are zero, admit everyone (minimizes rejections).

    Assumptions:
      - Exactly two constrained attributes (minCount each) over a fixed crowd size N=1000.
      - Attributes are boolean in `attrs` (missing -> False).
      - Rejection cap is handled by the caller; we track it for convenience.

    State tracked:
      K    : total admitted so far
      A,B  : counts of admits with attrA==True / attrB==True
      I    : overlap admits with both True
      R    : rejections so far (not used in the decision except for bookkeeping)
    """

    N: int = 1000  # venue size, per problem statement

    def __init__(
        self, scenario: int, constraints: list[dict], attribute_statistics: dict
    ):
        super().__init__(scenario, constraints, attribute_statistics)

        # Pull exactly two constrained attribute names
        keys = [k for k, v in self.min_required.items() if v > 0]
        if len(keys) != 2:
            raise ValueError(
                f"FeasibilityPreservingStrategy expects exactly two constrained attributes; got {len(keys)}"
            )
        self.attrA, self.attrB = keys[0], keys[1]

        # Hard counts required among the N admits
        self.A_min = int(self.min_required[self.attrA])
        self.B_min = int(self.min_required[self.attrB])
        # Overlap lower bound if rA + rB > 1: I_min = max(0, A_min + B_min - N)
        self.I_min = max(0, self.A_min + self.B_min - self.N)

        # Running counters
        self.K = 0
        self.A = 0
        self.B = 0
        self.I = 0
        self.R = 0  # rejections

    def _deficits_after_admit(self, a_flag: bool, b_flag: bool) -> tuple[int, int, int]:
        """Compute deficits (dA, dB, dI) if we admit a type with flags (a_flag, b_flag)."""
        A_prime = self.A + (1 if a_flag else 0)
        B_prime = self.B + (1 if b_flag else 0)
        I_prime = self.I + (1 if (a_flag and b_flag) else 0)

        dA = max(0, self.A_min - A_prime)
        dB = max(0, self.B_min - B_prime)
        dI = max(0, self.I_min - I_prime)
        return dA, dB, dI

    @staticmethod
    def _min_future_needed(dA: int, dB: int, dI: int) -> int:
        """
        Minimal number of future admits required to still be able to finish feasibly:
          X_min = max(dI, dA, dB, dA + dB - dI)
        """
        return max(dI, dA, dB, dA + dB - dI)

    def _should_admit(self, attrs: Dict[str, bool]) -> bool:
        """Core decision: admit iff capacity after admit >= minimal future needed."""
        a_flag = bool(attrs.get(self.attrA, False))
        b_flag = bool(attrs.get(self.attrB, False))

        # If already full, don't admit (defensive; caller should stop).
        if self.K >= self.N:
            return False

        # Compute deficits if we admit this person, and remaining capacity after admit.
        dA, dB, dI = self._deficits_after_admit(a_flag, b_flag)
        capacity_after_admit = self.N - (self.K + 1)
        x_min = self._min_future_needed(dA, dB, dI)

        # Admit iff feasibility is preserved.
        return capacity_after_admit >= x_min

    def decide(self, attrs: dict[str, bool]) -> bool:
        """
        Return True to admit, False to reject. Updates internal state.
        """
        admit = self._should_admit(attrs)

        if admit:
            # Update counters
            a_flag = bool(attrs.get(self.attrA, False))
            b_flag = bool(attrs.get(self.attrB, False))
            self.K += 1
            if a_flag:
                self.A += 1
            if b_flag:
                self.B += 1
            if a_flag and b_flag:
                self.I += 1
        else:
            self.R += 1  # track rejections (cap enforcement is external)

        return admit
