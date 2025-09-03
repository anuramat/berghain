from __future__ import annotations

from berghain.strategy_base import BaseStrategy


class Strategy(BaseStrategy):
    """
    Minimax-optimal for 2 attributes: rejects only when accepting would
    make it impossible to meet the minima in the worst case.
    Uses no probabilities; guaranteed-feasible if it's at all feasible.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # state
        self.admitted = 0
        self.a_count = 0
        self.b_count = 0

        # names (allow arbitrary attribute labels)
        keys = list(self.min_required.keys())
        assert len(keys) == 2, "Use this strategy only for exactly 2 attributes."
        self.A, self.B = keys[0], keys[1]

        self.RA = int(self.min_required[self.A])
        self.RB = int(self.min_required[self.B])

    def _deficits(self):
        dA = max(0, self.RA - self.a_count)
        dB = max(0, self.RB - self.b_count)
        return dA, dB

    def _remaining(self):
        return 1000 - self.admitted

    def _apply_accept(self, attrs):
        # update counts if we accept
        self.admitted += 1
        if attrs[self.A]:
            self.a_count += 1
        if attrs[self.B]:
            self.b_count += 1

    def decide(self, attrs: dict[str, bool]) -> bool:
        S = self._remaining()
        if S <= 0:
            return False  # capacity already full

        a = bool(attrs[self.A])
        b = bool(attrs[self.B])

        dA, dB = self._deficits()

        # Always accept if we've already met both minima
        if dA == 0 and dB == 0:
            self._apply_accept(attrs)
            return True

        # Casework following the reserve rule
        if a and b:
            # Helps both sides; safe to accept.
            self._apply_accept(attrs)
            return True

        if a and not b:
            # Accept iff S >= dA + dB
            if S >= dA + dB:
                self._apply_accept(attrs)
                return True
            return False

        if b and not a:
            # Symmetric
            if S >= dA + dB:
                self._apply_accept(attrs)
                return True
            return False

        # (0,0): Accept iff S >= dA + dB + 1
        if S >= dA + dB + 1:
            self._apply_accept(attrs)
            return True
        return False
