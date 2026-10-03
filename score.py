import argparse
import json
from pathlib import Path

from self_check import run_self_check


def run_score(rules_path: Path, lookups_path: Path, changes_path: Path, key: str | None = None) -> dict:
    result = run_self_check(rules_path, lookups_path, changes_path, Path("incial-data/dev/change_tests.json"))
    result["key_provided"] = bool(key)
    result["note"] = "This is a local structural self-check, not the official challenge score."
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Deprecated local checker retained for compatibility. Prefer self_check.py.")
    parser.add_argument("--key", default=None, help="Unused compatibility flag.")
    parser.add_argument("--rules", type=Path, default=Path("outputs/rules.json"))
    parser.add_argument("--lookups", type=Path, default=Path("outputs/lookups.json"))
    parser.add_argument("--changes", type=Path, default=Path("outputs/changes.json"))
    args = parser.parse_args()

    result = run_score(args.rules, args.lookups, args.changes, key=args.key)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
