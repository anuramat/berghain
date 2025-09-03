import argparse
import importlib
import json
import os
import random
import sys
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

BASE_URL = "https://berghain.challenges.listenlabs.ai/"


def _bool_str(b: bool) -> str:
    return "true" if b else "false"


def _get_json(path: str, params: dict) -> dict:
    url = urljoin(BASE_URL, path)
    if params:
        url += "?" + urlencode(params)
    req = Request(url, headers={"Accept": "application/json"})
    with urlopen(req) as r:
        return json.loads(r.read().decode())


def new_game(scenario: int, player_id: str) -> dict:
    return _get_json("new-game", {"scenario": scenario, "playerId": player_id})


def decide_and_next(game_id: str, person_index: int, accept: bool | None) -> dict:
    p = {"gameId": game_id, "personIndex": person_index}
    if accept is not None:
        p["accept"] = _bool_str(accept)
    return _get_json("decide-and-next", p)


def default_strategy_decide(person: dict, ctx: dict) -> bool:
    print("strategy ctx:", json.dumps(ctx, separators=(",", ":")))
    print("person:", json.dumps(person, separators=(",", ":")))
    return random.choice([True, False])


def load_strategy(spec: str | None):
    if not spec:
        return default_strategy_decide
    mod_name, _, func_name = spec.partition(":")
    if not mod_name or not func_name:
        raise SystemExit("--strategy must be 'module:function'")
    return getattr(importlib.import_module(mod_name), func_name)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", type=int, choices=[1, 2, 3], required=True)
    parser.add_argument("--strategy", help="module:function", default=None)
    args = parser.parse_args(argv)

    player_id = os.getenv("PLAYER_ID")
    if not player_id:
        print("PLAYER_ID env var is required", file=sys.stderr)
        return 1

    game = new_game(args.scenario, player_id)
    strategy = load_strategy(args.strategy)

    ctx = {
        "gameId": game["gameId"],
        "constraints": game.get("constraints"),
        "attributeStatistics": game.get("attributeStatistics"),
    }

    r = decide_and_next(ctx["gameId"], 0, None)
    while r.get("status") == "running":
        person = r["nextPerson"]
        decision = strategy(person, ctx)
        next_idx = person["personIndex"] + 1
        r = decide_and_next(ctx["gameId"], next_idx, decision)

    if r.get("status") == "completed":
        print("completed: rejectedCount=", r.get("rejectedCount"))
        return 0
    print("failed:", r)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
