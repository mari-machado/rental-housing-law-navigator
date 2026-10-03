from __future__ import annotations

import csv
import re
from datetime import date

from backend.core.config import settings
from backend.services.rule_service import load_rules


def normalize_text(value: str | None) -> str:
    if value is None:
        return ""
    lowered = value.strip().lower()
    return re.sub(r"[^a-z0-9]+", " ", lowered).strip()


def load_sample_addresses() -> list[dict]:
    csv_path = settings.data_dir / "sample_addresses.csv"
    if not csv_path.exists():
        return []

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def find_address_match(address: str) -> dict | None:
    normalized_target = normalize_text(address)
    if not normalized_target:
        return None

    for row in load_sample_addresses():
        normalized_row = normalize_text(row.get("street_address") or "")
        if normalized_target == normalized_row:
            return row
    return None


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
    return False


def _evaluate_rule(rule: dict, city: str, state: str, as_of: str) -> str:
    raw_status = str(rule.get("status") or "in_force")
    as_of_date = _parse_date(as_of)
    effective_date = _parse_date(rule.get("effective_date"))

    if raw_status == "pending":
        return "pending"
    if raw_status == "superseded":
        return "superseded"
    if raw_status == "not_yet_effective" and as_of_date and effective_date and as_of_date < effective_date:
        return "not_yet_effective"

    jur = str(rule.get("jurisdiction") or "").strip()
    if not jur:
        return "unknown"

    if "," in jur:
        return "applies" if _matches_city_or_state(jur, city, state) else "unknown"

    if jur.upper() == state.upper():
        return "applies"
    return "unknown"


def get_address_coverage(address: str, as_of: str = settings.as_of_date) -> dict:
    normalized = address.strip()
    if not normalized:
        return {"address": address, "as_of": as_of, "results": [], "message": "Address is required."}

    row = find_address_match(normalized)
    if row is None:
        return {
            "address": normalized,
            "as_of": as_of,
            "match_found": False,
            "results": [],
            "message": "Address not found in the provided sample dataset.",
            "not_legal_advice": True,
        }

    rules = load_rules(settings.project_root / "outputs" / "rules.json")
    state = (row.get("state") or "").upper()
    city = (row.get("postal_city") or "").strip()
    address_id = row.get("address_id", "unknown")

    results = []
    for rule in rules:
        result = _evaluate_rule(rule, city, state, as_of)
        results.append(
            {
                "team_rule_id": rule.get("team_rule_id"),
                "jurisdiction": rule.get("jurisdiction"),
                "title": rule.get("title"),
                "status": rule.get("status"),
                "result": result,
                "citation": rule.get("citation"),
                "source_url": rule.get("source_url"),
                "explanation": (
                    f"Rule {rule.get('team_rule_id')} was evaluated for {address_id} "
                    f"in {city}, {state} as of {as_of}."
                ),
            }
        )

    return {
        "address": normalized,
        "address_id": address_id,
        "jurisdiction": {"city": city, "state": state},
        "as_of": as_of,
        "match_found": True,
        "results": results[:10],
        "not_legal_advice": True,
    }


def list_sample_addresses(limit: int | None = 10) -> list[dict]:
    rows = load_sample_addresses()
    if limit is not None:
        return rows[:limit]
    return rows
