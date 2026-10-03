import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import DEFAULT_AS_OF, OUTPUTS_DIR, ensure_output_dir


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _normalize_jurisdiction(value: str) -> str:
    return " ".join((value or "").strip().split()).lower()


def _matches_city_or_state(rule_jurisdiction: str, city: str, state: str) -> bool:
    if not rule_jurisdiction:
        return False

    city_norm = (city or "").strip().lower()
    state_norm = (state or "").strip().lower()
    rule_norm = _normalize_jurisdiction(rule_jurisdiction)

    if not city_norm:
        return False

    if rule_norm == city_norm:
        return True
    if rule_norm == state_norm:
        return True
    if rule_norm.endswith(f", {state_norm}"):
        city_part = rule_norm.rsplit(",", 1)[0].strip()
        return city_part == city_norm
    if rule_norm.endswith(f", {city_norm}, {state_norm}"):
        return True
    return False


def _missing_coverage_fact(rule: dict, address: dict | None) -> bool:
    if not isinstance(address, dict):
        return False
    conditions_text = " ".join(
        [
            str(rule.get("coverage_conditions") or ""),
            str(rule.get("requirement") or ""),
            str(rule.get("interaction") or ""),
            str(rule.get("exemptions") or ""),
        ]
    ).lower()
    if "year_built" in conditions_text or "year built" in conditions_text or "building age" in conditions_text:
        if not str(address.get("year_built") or "").strip():
            return True
    if "units" in conditions_text or "unit count" in conditions_text or "unit" in conditions_text:
        if not str(address.get("units") or "").strip():
            return True
    if "owner" in conditions_text and "owner-occupied" in conditions_text:
        if not str(address.get("use_code") or "").strip():
            return True
    return False


def _evaluate_rule(rule: dict, city: str, state: str, as_of: str, address: dict | None = None) -> str:
    status = str(rule.get("status") or "in_force")
    if status == "pending":
        return "pending"
    if status == "superseded":
        return "superseded"
    if status == "not_yet_effective":
        effective = _parse_date(rule.get("effective_date"))
        as_of_date = _parse_date(as_of)
        if as_of_date and effective and as_of_date < effective:
            return "not_yet_effective"

    if _missing_coverage_fact(rule, address):
        return "unknown"

    rule_jurisdiction = str(rule.get("jurisdiction") or "").strip()
    if not rule_jurisdiction:
        return "unknown"

    if "," in rule_jurisdiction:
        return "applies" if _matches_city_or_state(rule_jurisdiction, city, state) else "unknown"

    if rule_jurisdiction.upper() == state.upper():
        return "applies"
    return "unknown"


def apply_rules(rules_path: Path, jurisdictions_path: Path, as_of: str = DEFAULT_AS_OF) -> dict:
    rules = json.loads(rules_path.read_text(encoding="utf-8")) if rules_path.exists() else []
    jurisdictions = json.loads(jurisdictions_path.read_text(encoding="utf-8")) if jurisdictions_path.exists() else []

    lookups: dict[str, list[dict]] = {}
    for address in jurisdictions:
        address_id = str(address.get("address_id", "unknown"))
        city = str(address.get("postal_city") or "").strip()
        state = str(address.get("state") or "").strip().upper()
        results: list[dict] = []
        for rule in rules:
            result = _evaluate_rule(rule, city, state, as_of, address)
            results.append(
                {
                    "team_rule_id": rule.get("team_rule_id"),
                    "jurisdiction": rule.get("jurisdiction"),
                    "result": result,
                    "status": rule.get("status"),
                    "explanation": f"Coverage assessed as of {as_of} for {address_id} in {city}, {state}.",
                    "conflict_flag": bool(rule.get("conflict_flag", False)),
                }
            )
        lookups[address_id] = results

    return {"as_of": as_of, "lookups": lookups}


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply rules to addresses and generate lookups.json.")
    parser.add_argument("--rules", type=Path, default=OUTPUTS_DIR / "rules.json")
    parser.add_argument("--jurisdictions", type=Path, default=OUTPUTS_DIR / "jurisdictions.json")
    parser.add_argument("--output", type=Path, default=OUTPUTS_DIR / "lookups.json")
    parser.add_argument("--as-of", default=DEFAULT_AS_OF)
    args = parser.parse_args()

    ensure_output_dir()
    output = apply_rules(args.rules, args.jurisdictions, args.as_of)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"count": len(output["lookups"]), "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
