# Berghain Game Client

- Run: `export PLAYER_ID=<uuid>; nix run . -- --scenario 1 [--strategy default]`
- Strategies live in `./strategies` and must define class `Strategy`.
- Loader resolves `--strategy <name>` to `strategies.<name>.Strategy`.

## Write a Strategy
Create `strategies/my_strategy.py`:

```python
from berghain.strategy_base import BaseStrategy

class Strategy(BaseStrategy):
    def __init__(self, constraints, attribute_statistics):
        super().__init__(constraints, attribute_statistics)

    def decide(self, person: dict) -> bool:
        attrs = person["attributes"]
        return attrs.get("well_dressed", False)
```

Run it:

```bash
export PLAYER_ID=<uuid>
nix run . -- --scenario 1 --strategy my_strategy
```

## Notes
- Default strategy: `--strategy default` (prints data, random decisions).
- BaseStrategy exposes: `min_required`, `relative_frequencies`, `correlations`.
- Quick test: `timeout 5s env PLAYER_ID=$PLAYER_ID nix run . -- --scenario 1 --strategy default || true`.
