import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import DATA_DIR, OUTPUTS_DIR, ensure_output_dir

CITY_ALIASES = {
    "Van Nuys": "Los Angeles",
    "Dorchester": "Boston",
    "South Boston": "Boston",
    "East Boston": "Boston",
    "Jersey city": "Jersey City",
    "Hoboken": "Hoboken",
    "Berkeley": "Berkeley",
    "Cambridge": "Cambridge",
    "Los Angeles": "Los Angeles",
}

COUNTY_BY_CITY_STATE = {
    ("Los Angeles", "CA"): "Los Angeles",
    ("Berkeley", "CA"): "Alameda",
    ("Boston", "MA"): "Suffolk",
    ("Cambridge", "MA"): "Middlesex",
    ("Hoboken", "NJ"): "Hudson",
    ("Jersey City", "NJ"): "Hudson",
    ("Newark", "NJ"): "Essex",
    ("Van Nuys", "CA"): "Los Angeles",
    ("Dorchester", "MA"): "Suffolk",
}


def _derive_legal_city(city: str) -> str:
    city_norm = (city or "").strip()
    if not city_norm:
        return city_norm
    return CITY_ALIASES.get(city_norm, city_norm)


def _derive_county(city: str, state: str) -> str | None:
    city_norm = (city or "").strip()
    state_norm = (state or "").strip().upper()
    return COUNTY_BY_CITY_STATE.get((city_norm, state_norm))


def geocode_addresses(data_dir: Path = DATA_DIR) -> list[dict]:
    csv_path = data_dir / "sample_addresses.csv"
    if not csv_path.exists():
        return []

    jurisdictions: list[dict] = []
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            city = (row.get("postal_city") or "").strip()
            state = (row.get("state") or "").strip()
            legal_city = _derive_legal_city(city)
            county = _derive_county(legal_city, state)
            jurisdiction = f"{legal_city}, {state}" if legal_city and state else state or "unknown"
            legal_jurisdiction = f"{legal_city}, {county}, {state}" if legal_city and county and state else jurisdiction
            jurisdictions.append(
                {
                    "address_id": row.get("address_id"),
                    "street_address": row.get("street_address"),
                    "postal_city": city,
                    "legal_city": legal_city,
                    "state": state,
                    "county": county,
                    "jurisdiction": jurisdiction,
                    "legal_jurisdiction": legal_jurisdiction,
                    "year_built": row.get("year_built"),
                    "units": row.get("units"),
                    "use_code": row.get("use_code"),
                }
            )
    return jurisdictions


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve addresses to jurisdiction records.")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--output", type=Path, default=OUTPUTS_DIR / "jurisdictions.json")
    args = parser.parse_args()

    ensure_output_dir()
    jurisdictions = geocode_addresses(args.data_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(jurisdictions, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"count": len(jurisdictions), "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
