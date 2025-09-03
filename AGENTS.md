# Repository Guidelines

## Project Structure & Module Organization
- `berghain/`: core client code
  - `api.py`: HTTP helpers and `BASE_URL`.
  - `cli.py`: CLI, game loop, strategy loading.
  - `strategy_base.py`: `BaseStrategy` constructor and normalized stats.
- `strategies/`: user strategies; each module exposes class `Strategy`.
- `README.md`: quick start; `CHALLENGE.md`: problem brief.

## Build, Test, and Development Commands
- `nix build`: builds the CLI app package.
- `nix run . -- --scenario 1 [--strategy <name>]`: runs the game.
- Quick dev run (timeout): `timeout 5s env PLAYER_ID=$PLAYER_ID nix run . -- --scenario 1 --strategy default || true`.
- `nix flake check`: evaluates flake and runs format check.
- `nix develop`: enter dev shell with Python and tools.
 - Logs: each run streams NDJSON to `logs/scenario{1,2,3}/<GAME_ID>.txt` (one `{attribute: boolean}` per line).

## Coding Style & Naming Conventions
- Python formatting via `nix fmt` (treefmt: black + isort).
- Nix files formatted with `nixfmt` (via `nix fmt`).
- Keep code concise; prefer stdlib; minimal boilerplate.
- Strategies: file `strategies/<name>.py` with class `Strategy(BaseStrategy)`.

## Testing Guidelines
- Framework: pytest (available in dev shell). Place tests under `tests/`.
- Name tests `test_*.py`; run with `pytest` inside `nix develop`.
- Aim for focused unit tests around strategy logic and API helpers (mock HTTP).

## Commit & Pull Request Guidelines
- Small, atomic commits; imperative, concise messages (e.g., `refactor: split CLI/API`).
- Run `nix fmt` before committing.
- PRs: include a brief description, rationale, and run commands/screenshots if relevant.

## Security & Configuration Tips
- Secrets: set `PLAYER_ID` via environment; avoid committing IDs or logs with sensitive data.
- Network calls use HTTPS only; base URL is constant in `api.py`.
 - Logs are written during the run; files may be partial if interrupted.

## Agent-Specific Instructions
- New strategies only specify module name with `--strategy <name>`; loader resolves `strategies.<name>.Strategy`.
- BaseStrategy stores: `min_required`, `relative_frequencies`, `correlations` for convenient access.
