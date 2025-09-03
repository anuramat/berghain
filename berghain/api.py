import json
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
