import argparse
import json
from pathlib import Path


REQUIRED_RULE_FIELDS = {
    "team_rule_id",
    "jurisdiction",
    "level",
    "category",
    "status",
    "title",
    "requirement",
    "citation",
    "source_url",
    "quoted_span",
}

REQUIRED_RESULT_VALUES = {"applies", "unknown", "pending", "not_yet_effective", "superseded"}


def _load_json(path: Path):
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _rule_statuses(rules):
    statuses = set()
    for rule in rules:
        if isinstance(rule, dict):
            statuses.add(str(rule.get("status") or "").lower())
    return statuses


def run_score(rules_path: Path, lookups_path: Path, changes_path: Path, key: str | None = None) -> dict:
    rules = _load_json(rules_path) or []
    lookups = _load_json(lookups_path) or {"lookups": {}}
    changes = _load_json(changes_path) or {}

    issues: list[str] = []
    if not isinstance(rules, list):
        issues.append("rules.json must be a JSON list.")
    else:
        if not rules:
            issues.append("rules.json is empty.")
        missing_fields = []
        for rule in rules:
            if not isinstance(rule, dict):
                missing_fields.append("non-object rule entry")
                continue
            missing = sorted(REQUIRED_RULE_FIELDS - set(rule.keys()))
            if missing:
                missing_fields.append(f"missing fields in rule: {missing}")
        if missing_fields:
            issues.extend(missing_fields[:5])

        statuses = _rule_statuses(rules)
        missing_statuses = sorted(REQUIRED_RESULT_VALUES - {"applies", "unknown", "pending", "not_yet_effective", "superseded"} & statuses)
        if missing_statuses:
            issues.append(f"No rule coverage values for {missing_statuses}.")

    if not isinstance(lookups, dict) or not isinstance(lookups.get("lookups"), dict):
        issues.append("lookups.json must contain an object with a 'lookups' dictionary.")
    elif not lookups["lookups"]:
        issues.append("lookups.json is empty.")

    if not isinstance(changes, dict):
        issues.append("changes.json must be an object keyed by test IDs.")
    elif not changes:
        issues.append("changes.json is empty.")

    if key is None:
        issues.append("No dev key provided; score is a local validation only.")

    score = max(0, 100 - len(issues) * 15)
    return {
        "score": score,
        "passed": score >= 80,
        "issues": issues,
        "key_provided": bool(key),
        "summary": {
            "rule_count": len(rules) if isinstance(rules, list) else 0,
            "lookup_count": len(lookups.get("lookups", {})) if isinstance(lookups, dict) and isinstance(lookups.get("lookups"), dict) else 0,
            "change_count": len(changes) if isinstance(changes, dict) else 0,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Local challenge validation for rules.json, lookups.json and changes.json.")
    parser.add_argument("--key", default=None, help="Optional dev key for the official challenge validation.")
    parser.add_argument("--rules", type=Path, default=Path("outputs/rules.json"))
    parser.add_argument("--lookups", type=Path, default=Path("outputs/lookups.json"))
    parser.add_argument("--changes", type=Path, default=Path("outputs/changes.json"))
    args = parser.parse_args()

    result = run_score(args.rules, args.lookups, args.changes, key=args.key)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
