from scipy.stats import binom

from berghain.strategy_base import BaseStrategy


class Strategy(BaseStrategy):
    def __init__(self, scenario, constraints, attribute_statistics):
        super().__init__(scenario, constraints, attribute_statistics)
        self.deficits = dict(self.min_required)
        self.remaining_places = 1000
        self.remaining_budget = self.max_rejections - 1

    def decide(self, attrs: dict[str, bool]) -> bool:
        person_attributes: list[str] = [k for k, v in attrs.items() if v]
        return self._decide(person_attributes)

    def _decide(self, attrs: list[str]) -> bool:
        self.log()

        # XXX obvious cases ----------------------------------------------------

        unmet_quotas: list[str] = [k for k, v in self.deficits.items() if v > 0]
        if not unmet_quotas:
            # atp we just need to get 1k in total
            return self._accept("we just need more people", attrs)

        contributes_to_deficit = any(k in unmet_quotas for k in attrs)
        if not contributes_to_deficit:
            # person is useless, safe to reject
            return self._reject("doesnt decrease deficits")

        has_all_attributes = len(attrs) == len(self.deficits)
        if has_all_attributes:
            return self._accept("all attributes", attrs)

        # XXX main logic -------------------------------------------------------

        # generally a good idea: think about constraint satisfaction probas
        # FUCK simplified idea: probability that there will be `deficit[k]` people with attribute `k` out of the next `remaining_budget + remaining_places` people
        remaining = (
            max(0, self.remaining_budget) + self.remaining_places
        )  # FUCK idk if this makes sense
        satisfaction_probas = {  # TODO actually "satisfiability", rename
            k: binom.logsf(v, remaining, self.relative_frequencies[k])
            for k, v in self.deficits.items()
        }  # FUCK might be v-1 actually, check
        print(
            "---", self.remaining_budget, self.deficits, satisfaction_probas
        )  # TODO move or remove?
        total_proba = sum(
            satisfaction_probas.values()
        )  # FUCK we're basically assuming here rejects are equiv to accepts; feels ok
        # FUCK ideally we would calculate reject vs accept, but we can't without a joint, so compare accept to average case or smth; feels ok
        accept_probas = {
            k: binom.logsf(
                v - (1 if k in attrs else 0),
                remaining - 1,
                self.relative_frequencies[k],
            )
            for k, v in self.deficits.items()
        }
        proba_diff = sum(accept_probas.values()) - total_proba  # - 0.05 # scenario 1
        if proba_diff < 0:
            return self._reject("decreases succ proba")
        return self._accept("doesn't decrease succ proba", attrs)

    def _reject(self, reason: str) -> bool:
        print(reason)
        self.remaining_budget -= 1
        if self.remaining_budget == 0:
            print("--- rejection budget exceeded ---")
        return False

    def _accept(self, reason: str, attrs: list[str]) -> bool:
        print(reason)
        self.remaining_places -= 1
        for k in attrs:
            if k in self.deficits and self.deficits[k] > 0:
                self.deficits[k] -= 1
        return True

    def log(self):
        pass  # TODO move unconditional logging here
