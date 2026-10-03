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

ALLOWED_STATUS = {"in_force", "not_yet_effective", "pending", "failed", "superseded"}
ALLOWED_RESULT = {"applies", "unknown", "pending", "not_yet_effective", "superseded"}


def _load_json(path: Path):
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _validate_rules(rules):
    issues = []
    if not isinstance(rules, list):
        return ["rules.json must be a JSON list."], 0

    if not rules:
        return ["rules.json is empty."], 0

    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            issues.append(f"rule[{index}] is not an object")
            continue
        missing = sorted(REQUIRED_RULE_FIELDS - set(rule.keys()))
        if missing:
            issues.append(f"rule[{index}] missing required fields: {missing}")
        status = str(rule.get("status") or "").lower()
        if status and status not in ALLOWED_STATUS:
            issues.append(f"rule[{index}] has invalid status: {status}")
        quoted = str(rule.get("quoted_span") or "").strip()
        if len(quoted) < 20:
            issues.append(f"rule[{index}] quoted_span is too short")
        citation = str(rule.get("citation") or "").strip()
        if not citation:
            issues.append(f"rule[{index}] citation is empty")
    return issues, len(rules)


def _validate_lookups(lookups):
    issues = []
    if not isinstance(lookups, dict):
        return ["lookups.json must be an object."], 0
    if not isinstance(lookups.get("lookups"), dict):
        return ["lookups.json must contain a 'lookups' object."], 0
    lookup_items = lookups["lookups"]
    if not lookup_items:
        return ["lookups.json has no addresses."], 0

    for address_id, entries in lookup_items.items():
        if not isinstance(entries, list):
            issues.append(f"address {address_id} does not map to a list")
            continue
        for idx, entry in enumerate(entries):
            if not isinstance(entry, dict):
                issues.append(f"address {address_id} entry[{idx}] is not an object")
                continue
            result = str(entry.get("result") or "").lower()
            if result and result not in ALLOWED_RESULT:
                issues.append(f"address {address_id} entry[{idx}] has invalid result: {result}")
    return issues, len(lookup_items)


def _validate_changes(changes):
    issues = []
    if not isinstance(changes, dict):
        return ["changes.json must be an object keyed by test IDs."], 0
    if not changes:
        return ["changes.json is empty."], 0
    for test_id, payload in changes.items():
        if not isinstance(payload, dict):
            issues.append(f"{test_id} must be an object")
            continue
        affected = payload.get("affected_address_ids")
        conflicts = payload.get("conflict_flag_address_ids")
        if not isinstance(affected, list):
            issues.append(f"{test_id} is missing affected_address_ids")
        if not isinstance(conflicts, list):
            issues.append(f"{test_id} is missing conflict_flag_address_ids")
    return issues, len(changes)


def _validate_tests(test_path: Path):
    issues = []
    if not test_path.exists():
        return [f"Missing test file: {test_path}"]
    tests = _load_json(test_path) or []
    if not isinstance(tests, list):
        return ["change_tests.json must be a list of test cases."]
    required_ids = {"T1", "T2", "T3", "T4", "T5"}
    found = {str(test.get("test_id")) for test in tests if isinstance(test, dict)}
    missing = sorted(required_ids - found)
    if missing:
        issues.append(f"Missing challenge tests: {missing}")
    return issues


def run_self_check(rules_path: Path, lookups_path: Path, changes_path: Path, tests_path: Path) -> dict:
    rules = _load_json(rules_path) or []
    lookups = _load_json(lookups_path) or {"lookups": {}}
    changes = _load_json(changes_path) or {}

    issues = []
    rule_issues, rule_count = _validate_rules(rules)
    lookup_issues, lookup_count = _validate_lookups(lookups)
    change_issues, change_count = _validate_changes(changes)
    test_issues = _validate_tests(tests_path)

    issues.extend(rule_issues)
    issues.extend(lookup_issues)
    issues.extend(change_issues)
    issues.extend(test_issues)

    return {
        "passed": not issues,
        "issues": issues,
        "summary": {
            "rule_count": rule_count,
            "address_count": lookup_count,
            "change_count": change_count,
            "tests_expected": ["T1", "T2", "T3", "T4", "T5"],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Local structural self-check for the challenge outputs.")
    parser.add_argument("--rules", type=Path, default=Path("outputs/rules.json"))
    parser.add_argument("--lookups", type=Path, default=Path("outputs/lookups.json"))
    parser.add_argument("--changes", type=Path, default=Path("outputs/changes.json"))
    parser.add_argument("--tests", type=Path, default=Path("incial-data/dev/change_tests.json"))
    args = parser.parse_args()

    result = run_self_check(args.rules, args.lookups, args.changes, args.tests)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
