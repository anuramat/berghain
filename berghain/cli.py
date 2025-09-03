import argparse
import importlib
import os
import sys

from .api import decide_and_next, new_game


def load_strategy(module_name: str | None, constraints, attribute_statistics):
    mod = f"strategies.{module_name or 'default'}"
    cls = getattr(importlib.import_module(mod), "Strategy")
    return cls(constraints, attribute_statistics)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--scenario", type=int, choices=[1, 2, 3], required=True)
    p.add_argument(
        "--strategy",
        help="module in strategies/ containing class Strategy (default: default)",
        default=None,
    )
    args = p.parse_args(argv)

    player_id = os.getenv("PLAYER_ID")
    if not player_id:
        print("PLAYER_ID env var is required", file=sys.stderr)
        return 1

    game = new_game(args.scenario, player_id)
    strategy = load_strategy(
        args.strategy, game.get("constraints"), game.get("attributeStatistics")
    )

    game_id = game["gameId"]
    r = decide_and_next(game_id, 0, None)
    while r.get("status") == "running":
        person = r["nextPerson"]
        decision = strategy.decide(person)
        r = decide_and_next(game_id, person["personIndex"], decision)

    if r.get("status") == "completed":
        print("completed: rejectedCount=", r.get("rejectedCount"))
        return 0
    print("failed:", r)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
