# Repository Guidelines

official problem description:

@CHALLENGE.md

user notes, should be prioritized over anything else:

@NOTES.md

base class for strategies:

@berghain/strategy_base.py

## Project Structure & Module Organization

- `berghain/`: core client code
  - `api.py`: HTTP helpers and `BASE_URL`.
  - `cli.py`: CLI, game loop, strategy loading.
  - `strategy_base.py`: `BaseStrategy` constructor
- `strategies/`: user strategies; each module exposes class `Strategy`.

## Build, Test, and Development Commands

- to test a strategy: `make test1`, `make test2`, `make test3` for scenario 1, 2, 3
  - these use local test runs under the hood, so as to avoid using the API (it's
    very slow); so ONLY use these three commands to test the strategies
- Python and nix formatting are launched with `nix fmt`

## Strategies

- each strategy is a file `strategies/<name>.py` with class `Strategy(BaseStrategy)`
- strategies are launched with `--strategy <name>`; loader resolves `strategies.<name>.Strategy`.

## Logs

- files: each run streams NDJSON to `logs/scenario{1,2,3}/<GAME_ID>.txt` (one `{attribute: boolean}` per line).
- stdout: prints `game_id: <UUID>` on start/resume and `decision: idx=<N> accept=<True|False>` per decision.

## Configuration Tips

- Secrets: set `PLAYER_ID` via environment
- Network calls use HTTPS; base URL is constant in `api.py`.
- Logs are written during the run; files may be partial if interrupted.
