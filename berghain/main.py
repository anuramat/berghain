import argparse
import importlib
import json
import os
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


class BaseStrategy:
    def __init__(self, constraints: list[dict], attribute_statistics: dict):
        self.min_required = {c["attribute"]: c["minCount"] for c in (constraints or [])}
        self.relative_frequencies = (attribute_statistics or {}).get(
            "relativeFrequencies", {}
        )
        self.correlations = (attribute_statistics or {}).get("correlations", {})


def load_strategy(
    spec: str | None, constraints: list[dict], attribute_statistics: dict
):
    if not spec:
        spec = "berghain.default_strategy:DefaultStrategy"
    mod_name, _, cls_name = spec.partition(":")
    if not mod_name or not cls_name:
        raise SystemExit("--strategy must be 'module:ClassName'")
    cls = getattr(importlib.import_module(mod_name), cls_name)
    return cls(constraints, attribute_statistics)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", type=int, choices=[1, 2, 3], required=True)
    parser.add_argument(
        "--strategy",
        help="module:ClassName (default: default_strategy:DefaultStrategy)",
        default=None,
    )
    args = parser.parse_args(argv)

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
