import argparse
import importlib
import json
import os
import re
import sys
from pathlib import Path
from urllib.error import HTTPError

from .api import decide_and_next, new_game


def format_decision_log(idx: int, decision: bool, attrs: dict[str, bool]) -> str:
    action = "accept" if decision else "reject"
    true_attrs = [attr for attr, value in attrs.items() if value]
    attrs_str = " ".join(true_attrs)
    return f"{idx:4d}: {action}; {attrs_str}"


def load_strategy(module_name: str | None, scenario, constraints, attribute_statistics):
    mod = f"strategies.{module_name or 'default'}"
    cls = getattr(importlib.import_module(mod), "Strategy")
    return cls(scenario, constraints, attribute_statistics)


def analyze_log(log_file: str) -> int:
    from collections import defaultdict

    counts = defaultdict(int)
    total = 0

    try:
        with open(log_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                attrs = json.loads(line)
                true_attrs = tuple(
                    sorted(attr for attr, value in attrs.items() if value)
                )
                counts[true_attrs] += 1
                total += 1
    except FileNotFoundError:
        print(f"Error: log file not found: {log_file}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON in log file: {e}", file=sys.stderr)
        return 1

    print(f"Attribute combination statistics from {log_file}:")
    print()

    for attrs, count in sorted(counts.items()):
        if not attrs:
            print(f"No attributes: {count}")
        else:
            attrs_str = ", ".join(attrs)
            print(f"Only {attrs_str}: {count}")

    print()
    print(f"Total: {total}")

    verification = sum(counts.values())
    if verification != total:
        print(f"Warning: sum mismatch {verification} != {total}", file=sys.stderr)

    return 0


def test_run(log_file: str, scenario: int, strategy_name: str) -> int:
    if not scenario:
        print("Error: --scenario is required for test run", file=sys.stderr)
        return 1

    # Read meta from cache (test runs never call API)
    log_dir = Path("logs") / f"scenario{scenario}"
    meta_cache_path = log_dir / "meta.json"

    if not meta_cache_path.exists():
        print(
            f"Error: meta cache not found at {meta_cache_path}. Run a real game first to generate cache.",
            file=sys.stderr,
        )
        return 1

    try:
        with meta_cache_path.open("r") as f:
            meta = json.load(f)

        strategy = load_strategy(
            strategy_name,
            scenario,
            meta.get("constraints"),
            meta.get("attributeStatistics"),
        )
    except Exception as e:
        print(f"Error initializing strategy: {e}", file=sys.stderr)
        return 1

    total_accepts = 0
    total_rejects = 0
    accepted_attributes = {}

    for attr in strategy.min_required.keys():
        accepted_attributes[attr] = 0

    try:
        with open(log_file, "r") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    attrs = json.loads(line)
                except json.JSONDecodeError as e:
                    print(
                        f"Error parsing JSON on line {line_num}: {e}", file=sys.stderr
                    )
                    return 1

                decision = strategy.decide(attrs)

                if decision:
                    total_accepts += 1
                    for attr, value in attrs.items():
                        if value and attr in accepted_attributes:
                            accepted_attributes[attr] += 1
                    if total_accepts >= 1000:
                        break
                else:
                    total_rejects += 1

    except FileNotFoundError:
        print(f"Error: log file not found: {log_file}", file=sys.stderr)
        return 1

    print(f"Test run results for {log_file}:")
    print(f"Total accepts: {total_accepts}")
    print(f"Total rejects: {total_rejects}")
    print()

    print("Attribute completion rates:")
    for attr, required in strategy.min_required.items():
        actual = accepted_attributes[attr]
        rate = actual / required if required > 0 else 0
        print(f"{attr}: {actual}/{required} ({rate:.2%})")

    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--scenario", type=int, choices=[1, 2, 3])
    p.add_argument(
        "--strategy",
        help="module in strategies/ containing class Strategy (default: default)",
        default=None,
    )
    p.add_argument(
        "--resume",
        help="resume an existing game by gameId; replays logs to rebuild strategy state",
        default=None,
    )
    p.add_argument(
        "--analyze-log",
        help="analyze a log file and show attribute combination statistics",
        default=None,
    )
    p.add_argument(
        "--test-run",
        help="test run strategy on a log file without API calls",
        default=None,
    )
    args = p.parse_args(argv)

    if args.analyze_log:
        return analyze_log(args.analyze_log)

    if args.test_run:
        return test_run(args.test_run, args.scenario, args.strategy)

    if not args.scenario:
        p.error("--scenario is required when not using --analyze-log or --test-run")

    player_id = os.getenv("PLAYER_ID")
    if not player_id:
        print("PLAYER_ID env var is required", file=sys.stderr)
        return 1

    # Always fetch constraints/stats to construct the strategy deterministically
    meta = new_game(args.scenario, player_id)
    strategy = load_strategy(
        args.strategy,
        args.scenario,
        meta.get("constraints"),
        meta.get("attributeStatistics"),
    )

    log_dir = Path("logs") / f"scenario{args.scenario}"
    log_dir.mkdir(parents=True, exist_ok=True)

    # Save meta to cache (real runs always write, never read)
    meta_cache_path = log_dir / "meta.json"
    with meta_cache_path.open("w") as f:
        json.dump(
            {
                "constraints": meta.get("constraints"),
                "attributeStatistics": meta.get("attributeStatistics"),
            },
            f,
        )

    if args.resume:
        game_id = args.resume
        log_path = log_dir / f"{game_id}.txt"
        print(f"game_id: {game_id}")
        try:
            r = decide_and_next(game_id, 0, None)
        except HTTPError as e:
            body = e.read().decode(errors="ignore")
            try:
                msg = json.loads(body).get("error", "")
            except Exception:
                msg = body
            m = re.search(r"Expected person (\d+)", msg or "")
            if not m:
                print("failed:", msg or str(e))
                return 2
            idx = int(m.group(1))
            lines = []
            if log_path.exists():
                with log_path.open() as f:
                    lines = [ln.strip() for ln in f if ln.strip()]
            # Rebuild state by replaying prior people
            for i in range(min(idx, len(lines))):
                strategy.decide(json.loads(lines[i]))
            if idx >= len(lines):
                print("failed: missing attributes for expected person", file=sys.stderr)
                return 2
            decision = strategy.decide(json.loads(lines[idx]))
            print(format_decision_log(idx, decision, json.loads(lines[idx])))
            r = decide_and_next(game_id, idx, decision)
    else:
        game = meta
        game_id = game["gameId"]
        log_path = log_dir / f"{game_id}.txt"
        print(f"game_id: {game_id}")
        r = decide_and_next(game_id, 0, None)

    with log_path.open("a") as lf:
        while r.get("status") == "running":
            person = r["nextPerson"]
            lf.write(
                json.dumps(person.get("attributes", {}), separators=(",", ":")) + "\n"
            )
            lf.flush()
            decision = strategy.decide(person["attributes"])
            print(
                format_decision_log(
                    person["personIndex"], decision, person["attributes"]
                )
            )
            r = decide_and_next(game_id, person["personIndex"], decision)
    if r.get("status") == "completed":
        print("completed: rejectedCount=", r.get("rejectedCount"))
        return 0
    print("failed:", r)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
