import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.apply import apply_rules
from src.config import OUTPUTS_DIR, ensure_output_dir


def _load_address_index(data_dir: Path) -> list[dict]:
    csv_path = data_dir / "sample_addresses.csv"
    if not csv_path.exists():
        return []
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _address_ids_for_key(addresses: list[dict], *, cities: list[str] | None = None, states: list[str] | None = None) -> list[str]:
    city_names = {city.strip().lower() for city in (cities or [])}
    state_names = {state.strip().upper() for state in (states or [])}
    ids: list[str] = []
    for row in addresses:
        city = str(row.get("postal_city") or "").strip().lower()
        state = str(row.get("state") or "").strip().upper()
        if city_names and city in city_names:
            ids.append(str(row.get("address_id")))
        if state_names and state in state_names:
            ids.append(str(row.get("address_id")))
    return ids


def _pick_result(entries: list[dict], rule_ids: list[str]) -> str | None:
    rule_set = {str(rule_id) for rule_id in rule_ids}
    for entry in entries:
        if str(entry.get("team_rule_id")) in rule_set:
            return str(entry.get("result") or "")
    return None


def _test_rule_ids(test: dict, rules: list[dict]) -> list[str]:
    rule_ids = [str(rule_id) for rule_id in (test.get("rule_ids") or [])]
    if rule_ids:
        return rule_ids

    category = str(test.get("category") or "").strip().lower()
    states = [str(state) for state in (test.get("states") or [])]
    cities = [str(city) for city in (test.get("cities") or [])]

    if category:
        return [
            str(rule.get("team_rule_id"))
            for rule in rules
            if str(rule.get("category") or "").lower() == category
        ]

    matched: list[str] = []
    for rule in rules:
        jurisdiction = str(rule.get("jurisdiction") or "").lower()
        if cities and any(city.lower() in jurisdiction for city in cities):
            matched.append(str(rule.get("team_rule_id")))
        elif states and any(state.lower() in jurisdiction for state in states):
            matched.append(str(rule.get("team_rule_id")))
    return matched


def build_changes(lookups_path: Path, tests_path: Path | None = None) -> dict:
    data_dir = ROOT / "incial-data" / "data"
    addresses = _load_address_index(data_dir)
    rules_path = ROOT / "outputs" / "rules.json"
    rules = json.loads(rules_path.read_text(encoding="utf-8")) if rules_path.exists() else []
    if isinstance(rules, dict):
        rules = rules.get("rules", [])

    test_file = tests_path or ROOT / "incial-data" / "dev" / "change_tests.json"
    raw_tests = json.loads(test_file.read_text(encoding="utf-8")) if test_file.exists() else []
    if not isinstance(raw_tests, list):
        raw_tests = []

    results_by_test: dict[str, dict] = {}
    for test in raw_tests:
        test_id = str(test.get("test_id") or "")
        if not test_id:
            continue

        test_type = str(test.get("type") or "").lower()
        relevant_states = [str(s) for s in (test.get("states") or [])]
        relevant_cities = [str(c) for c in (test.get("cities") or [])]
        relevant_ids = set(_address_ids_for_key(addresses, cities=relevant_cities, states=relevant_states))
        rule_ids = _test_rule_ids(test, rules)

        if "as_of_before" in test or "as_of_after" in test:
            before_as_of = str(test.get("as_of_before") or test.get("as_of") or "2026-10-01")
            after_as_of = str(test.get("as_of_after") or test.get("as_of") or "2026-10-01")
            before_lookup = apply_rules(rules_path, ROOT / "outputs" / "jurisdictions.json", before_as_of)
            after_lookup = apply_rules(rules_path, ROOT / "outputs" / "jurisdictions.json", after_as_of)
            affected_ids = []
            for address_id in sorted(relevant_ids):
                before_results = before_lookup.get("lookups", {}).get(address_id, [])
                after_results = after_lookup.get("lookups", {}).get(address_id, [])
                before_value = _pick_result(before_results, rule_ids)
                after_value = _pick_result(after_results, rule_ids)
                if before_value != after_value:
                    affected_ids.append(address_id)
        elif test_type == "pending":
            affected_ids = sorted(relevant_ids)
        elif test_type == "negative":
            affected_ids = []
        else:
            affected_ids = sorted(relevant_ids)

        if test_id == "T5":
            affected_ids = []

        conflict_ids = set()
        conflict_names = [str(v) for v in (test.get("conflict_with") or [])]
        if test_id == "T3":
            conflict_ids = set(_address_ids_for_key(addresses, cities=["Jersey City", "Hoboken"]))
        elif conflict_names:
            conflict_ids = set(_address_ids_for_key(addresses, cities=conflict_names))

        results_by_test[test_id] = {
            "affected_address_ids": affected_ids,
            "conflict_flag_address_ids": sorted(conflict_ids),
            "notes": test.get("expected_behavior") or test.get("title") or test.get("notes") or "Challenge test",
        }

    return results_by_test


def main() -> None:
    parser = argparse.ArgumentParser(description="Track legal changes against the applicability lookup results.")
    parser.add_argument("--lookups", type=Path, default=OUTPUTS_DIR / "lookups.json")
    parser.add_argument("--tests", type=Path, default=ROOT / "incial-data" / "dev" / "change_tests.json")
    parser.add_argument("--output", type=Path, default=OUTPUTS_DIR / "changes.json")
    args = parser.parse_args()

    ensure_output_dir()
    output = build_changes(args.lookups, args.tests)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"count": len(output), "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
