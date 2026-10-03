from __future__ import annotations

import csv
import re

from backend.core.config import settings
from backend.services.rule_service import load_rules
from src.apply import evaluate_rule


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
        result = evaluate_rule(rule, city, state, as_of, row)
        if result is None:
            continue
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
