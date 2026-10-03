import argparse
import json
import re
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
    if "," in rule_norm:
        city_part, state_part = [part.strip() for part in rule_norm.rsplit(",", 1)]
        if city_part == city_norm and state_part == state_norm:
            return True
        if state_part == state_norm and city_part == city_norm:
            return True
    return False


def _extract_numeric_threshold(text: str, *, field: str) -> int | None:
    patterns = [
        rf"(?:before|on or before|prior to|not later than)\s*(\d{{4}})",
        rf"(?:after|on or after|later than)\s*(\d{{4}})",
        rf"(\d{{4}})\s*(?:cutoff|threshold|year)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                continue
    if field == "units":
        for match in re.finditer(r"(\d+)\s*(?:\+|or more|or fewer|units?|dwelling units?)", text, flags=re.IGNORECASE):
            try:
                return int(match.group(1))
            except ValueError:
                continue
    return None


def _rule_requires_fact(rule: dict, fact_name: str) -> bool:
    text = " ".join([
        str(rule.get("coverage_conditions") or ""),
        str(rule.get("requirement") or ""),
        str(rule.get("exemptions") or ""),
        str(rule.get("interaction") or ""),
    ]).lower()
    return fact_name in text or fact_name.replace("_", " ") in text


def _coverage_status(rule: dict, address: dict | None) -> str | None:
    if not isinstance(address, dict):
        return None

    text = " ".join([
        str(rule.get("coverage_conditions") or ""),
        str(rule.get("requirement") or ""),
        str(rule.get("exemptions") or ""),
        str(rule.get("interaction") or ""),
    ])
    text_lower = text.lower()

    if "year built" in text_lower or "certificate" in text_lower or "built before" in text_lower or "before" in text_lower and "year" in text_lower:
        year_built = address.get("year_built")
        if not year_built:
            return "unknown"
        threshold = _extract_numeric_threshold(text, field="year")
        if threshold is not None:
            try:
                year_int = int(str(year_built).strip())
                if "before" in text_lower or "on or before" in text_lower or "prior to" in text_lower:
                    return "applies" if year_int <= threshold else None
                if "after" in text_lower or "later than" in text_lower:
                    return "applies" if year_int > threshold else None
            except ValueError:
                pass

    if "unit" in text_lower and "unit count" in text_lower or "units" in text_lower or "dwelling" in text_lower:
        units = address.get("units")
        if units in (None, "", "unknown"):
            return "unknown"
        try:
            units_int = int(str(units).strip())
        except ValueError:
            return "unknown"
        threshold = _extract_numeric_threshold(text, field="units")
        if threshold is not None:
            if "5 or more" in text_lower or "5+" in text_lower or "five or more" in text_lower:
                return "applies" if units_int >= threshold else None
            if "2 or fewer" in text_lower or "two or fewer" in text_lower:
                return "applies" if units_int <= threshold else None
            if "under" in text_lower and "units" in text_lower:
                return "applies" if units_int < threshold else None

    if "owner-occupied" in text_lower or "owner occupied" in text_lower or "small-landlord" in text_lower:
        if not address.get("use_code"):
            return "unknown"

    return "applies"


def evaluate_rule(rule: dict, city: str, state: str, as_of: str, address: dict | None = None) -> str | None:
    rule_jurisdiction = str(rule.get("jurisdiction") or "").strip()
    if not rule_jurisdiction:
        return None

    if not _matches_city_or_state(rule_jurisdiction, city, state):
        return "unknown"

    status = str(rule.get("status") or "in_force").strip().lower()
    if status == "pending":
        return "pending"
    if status == "superseded":
        return "superseded"
    if status == "failed":
        return None

    effective_date = _parse_date(rule.get("effective_date"))
    as_of_date = _parse_date(as_of)
    if effective_date and as_of_date and effective_date > as_of_date:
        return "not_yet_effective"

    coverage_result = _coverage_status(rule, address)
    if coverage_result == "unknown":
        return "unknown"
    if coverage_result is None:
        if not any(str(rule.get(field) or "").strip() for field in ("coverage_conditions", "requirement", "exemptions", "interaction", "key_value")):
            return "applies"
        return "unknown"

    return "applies"


# Backward-compatible alias used by the challenge tests and older code paths.
_evaluate_rule = evaluate_rule


def apply_rules(rules_path: Path, jurisdictions_path: Path, as_of: str = DEFAULT_AS_OF) -> dict:
    rules = json.loads(rules_path.read_text(encoding="utf-8")) if rules_path.exists() else []
    jurisdictions = json.loads(jurisdictions_path.read_text(encoding="utf-8")) if jurisdictions_path.exists() else []
    if isinstance(rules, dict):
        rules = rules.get("rules", [])

    lookups: dict[str, list[dict]] = {}
    for address in jurisdictions:
        address_id = str(address.get("address_id", "unknown"))
        city = str(address.get("postal_city") or "").strip()
        state = str(address.get("state") or "").strip().upper()
        results: list[dict] = []
        for rule in rules:
            result = evaluate_rule(rule, city, state, as_of, address)
            if result is None:
                continue
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
