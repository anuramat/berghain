# Repository Guidelines

## Project Structure & Module Organization

- `berghain/`: core client code
  - `api.py`: HTTP helpers and `BASE_URL`.
  - `cli.py`: CLI, game loop, strategy loading.
  - `strategy_base.py`: `BaseStrategy` constructor
- `strategies/`: user strategies; each module exposes class `Strategy`.

## Build, Test, and Development Commands

- `nix run . -- --scenario <num> --strategy <name>`: runs the game.
  - a single run takes about 15 minutes, so don't run it yourself unless
    explicitly instructed
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
