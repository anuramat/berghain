import json
import time
from urllib.error import HTTPError, URLError
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
    delay = 1.0
    for _ in range(8):
        try:
            with urlopen(req, timeout=999) as r:
                return json.loads(r.read().decode())
        except HTTPError as e:
            if e.code in (429, 500, 502, 503, 504):
                print(f"HTTPError {e.code}, retrying in {delay}s")
                time.sleep(delay)
                delay = min(10.0, delay * 2)
                continue
            raise
        except URLError as e:
            print(f"URLError {e}, retrying in {delay}s")
            time.sleep(delay)
            delay = min(10.0, delay * 2)
    # last attempt
    with urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())


def new_game(scenario: int, player_id: str) -> dict:
    return _get_json("new-game", {"scenario": scenario, "playerId": player_id})


def decide_and_next(game_id: str, person_index: int, accept: bool | None) -> dict:
    p = {"gameId": game_id, "personIndex": person_index}
    if accept is not None:
        p["accept"] = _bool_str(accept)
    return _get_json("decide-and-next", p)
