import argparse
import json
from pathlib import Path


def _load_json(path: Path):
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def run_score(rules_path: Path, lookups_path: Path, changes_path: Path) -> dict:
    rules = _load_json(rules_path)
    lookups = _load_json(lookups_path)
    changes = _load_json(changes_path)

    issues = []
    if not isinstance(rules, list):
        issues.append("rules.json is not a list")
    if not isinstance(lookups, dict) or "lookups" not in lookups:
        issues.append("lookups.json does not include a 'lookups' object")
    if not isinstance(changes, dict):
        issues.append("changes.json is not an object")

    required_statuses = {"applies", "pending", "unknown", "not_yet_effective", "superseded"}
    if isinstance(rules, list):
        statuses = {str(rule.get("status") or "").lower() for rule in rules if isinstance(rule, dict)}
        missing_statuses = sorted(required_statuses - statuses)
        if missing_statuses:
            issues.append(f"Missing statuses in rules output: {missing_statuses}")

    score = max(0, 100 - len(issues) * 20)
    return {
        "score": score,
        "passed": score >= 80,
        "issues": issues,
        "summary": {
            "rule_count": len(rules) if isinstance(rules, list) else 0,
            "lookup_count": len(lookups.get("lookups", {})) if isinstance(lookups, dict) and isinstance(lookups.get("lookups"), dict) else 0,
            "change_count": len(changes) if isinstance(changes, dict) else 0,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the generated challenge outputs.")
    parser.add_argument("--key", default=None, help="Optional dev key for challenge validation.")
    parser.add_argument("--rules", type=Path, default=Path("outputs/rules.json"))
    parser.add_argument("--lookups", type=Path, default=Path("outputs/lookups.json"))
    parser.add_argument("--changes", type=Path, default=Path("outputs/changes.json"))
    args = parser.parse_args()

    result = run_score(args.rules, args.lookups, args.changes)
    if args.key:
        result["key_provided"] = True
    else:
        result["key_provided"] = False
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
