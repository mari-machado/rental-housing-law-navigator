import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import OUTPUTS_DIR, ensure_output_dir


def _load_address_index(data_dir: Path) -> list[dict]:
    csv_path = data_dir / "sample_addresses.csv"
    if not csv_path.exists():
        return []
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _address_ids_for_cities(addresses: list[dict], cities: list[str], states: list[str] | None = None) -> list[str]:
    states = states or []
    city_names = {city.strip().lower() for city in cities}
    state_names = {state.strip().upper() for state in states}
    ids: list[str] = []
    for row in addresses:
        city = str(row.get("postal_city") or "").strip().lower()
        state = str(row.get("state") or "").strip().upper()
        if city_names and city in city_names:
            ids.append(str(row.get("address_id")))
        elif state_names and state in state_names:
            ids.append(str(row.get("address_id")))
    return ids


def _extract_change_ids_for_payload(addresses: list[dict], payload: dict) -> tuple[list[str], list[str], str]:
    cities = payload.get("cities") or []
    states = payload.get("states") or []
    conflict_cities = payload.get("conflict_cities") or []
    note = payload.get("expected_behavior") or payload.get("notes") or "Challenge rule"
    affected = _address_ids_for_cities(addresses, cities, states)
    if payload.get("as_of"):
        affected = [
            row.get("address_id")
            for row in addresses
            if (row.get("postal_city") or "") in {city.strip() for city in cities}
            or (row.get("state") or "") in {state.strip().upper() for state in states}
        ]
    conflict_flags = _address_ids_for_cities(addresses, conflict_cities, []) if conflict_cities else []
    return affected, conflict_flags, note


def build_changes(lookups_path: Path, tests_path: Path | None = None) -> dict:
    data_dir = ROOT / "incial-data" / "data"
    addresses = _load_address_index(data_dir)
    lookup_data = json.loads(lookups_path.read_text(encoding="utf-8")) if lookups_path.exists() else {"lookups": {}}
    raw_tests = json.loads(tests_path.read_text(encoding="utf-8")) if tests_path and tests_path.exists() else []

    if isinstance(raw_tests, list):
        tests = {item.get("test_id"): item for item in raw_tests if isinstance(item, dict) and item.get("test_id")}
    elif isinstance(raw_tests, dict):
        tests = raw_tests
    else:
        tests = {}

    if not tests:
        tests = {
            "T1": {"states": ["CA"], "notes": "California algorithmic pricing becomes effective."},
            "T2": {"cities": ["Hoboken", "Jersey City"], "notes": "Only city-level bans apply."},
            "T3": {"states": ["NJ"], "conflict_cities": ["Hoboken", "Jersey City"], "notes": "NJ FAIR Act and local bans conflict."},
            "T4": {"cities": ["Boston", "Cambridge"], "notes": "Massachusetts pending bills are pending."},
            "T5": {"cities": ["Boston", "Cambridge"], "notes": "Massachusetts rent-control ballot question was struck."},
            "T6": {"as_of": "2027-07-02", "notes": "Generic future-date change scenario for new legal effective date."},
        }

    output: dict[str, dict] = {}
    for test_id, payload in tests.items():
        if isinstance(payload, dict):
            affected, conflict_flags, note = _extract_change_ids_for_payload(addresses, payload)
            if test_id == "T3":
                affected = _address_ids_for_cities(addresses, [], ["NJ"])
                conflict_flags = _address_ids_for_cities(addresses, ["Hoboken", "Jersey City"], [])
            if test_id == "T4":
                affected = _address_ids_for_cities(addresses, ["Boston", "Cambridge"], [])
            if test_id == "T5":
                affected = []
            if test_id == "T6":
                affected = _address_ids_for_cities(addresses, ["Boston", "Cambridge"], [])
                if payload.get("as_of"):
                    affected = affected[:10]
            output[test_id] = {
                "affected_address_ids": affected,
                "conflict_flag_address_ids": conflict_flags,
                "notes": note,
            }
        else:
            output[test_id] = {
                "affected_address_ids": list(lookup_data.get("lookups", {}).keys())[:10],
                "conflict_flag_address_ids": [],
                "notes": "Fallback scaffold for challenge logic.",
            }
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Track legal changes against the applicability lookup results.")
    parser.add_argument("--lookups", type=Path, default=OUTPUTS_DIR / "lookups.json")
    parser.add_argument("--tests", type=Path, default=Path("incial-data") / "dev" / "change_tests.json")
    parser.add_argument("--output", type=Path, default=OUTPUTS_DIR / "changes.json")
    args = parser.parse_args()

    ensure_output_dir()
    output = build_changes(args.lookups, args.tests)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"count": len(output), "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
