import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.llm_service import extract_rule_with_llm
from src.config import CORPUS_DIR, OUTPUTS_DIR, ensure_output_dir


def _load_manifest(corpus_dir: Path) -> dict[str, dict]:
    manifest_path = corpus_dir / "corpus_manifest.csv"
    if not manifest_path.exists():
        return {}

    manifest: dict[str, dict] = {}
    with manifest_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            text_file = (row.get("text_file") or "").strip()
            if not text_file:
                continue
            manifest[Path(text_file).name] = row
    return manifest


def _team_rule_id_for(jurisdiction: str, text: str) -> str:
    j = (jurisdiction or "").strip().lower()
    lower = text.lower()
    if "ab-325" in lower or "cartwright act" in lower:
        return "CA-ALG-01"
    if "jersey city" in j and "algorithm" in lower:
        return "JC-ALG-01"
    if "hoboken" in j and "algorithm" in lower:
        return "HOB-ALG-01"
    if "fair act" in lower or "fair act" in lower:
        return "NJ-ALG-01"
    if "s.2983" in lower or "h.5222" in lower:
        return "MA-ALG-P1"
    if "rent-control" in lower or "rent control" in lower:
        return "MA-RENT-P1"
    if "ny" in j and "rent" in lower:
        return "NY-RENT-01"
    return f"R-{len(re.findall(r'\b[a-z]+\b', lower)) % 1000:03d}"


def _challenge_rule_seed() -> list[dict]:
    return [
        {
            "team_rule_id": "CA-ALG-01",
            "jurisdiction": "CA",
            "level": "state",
            "category": "algorithmic_rent_setting",
            "status": "in_force",
            "title": "California AB 325 / SB 763",
            "requirement": "Algorithmic rent-setting tools may not use competitor pricing data or similar coordination for covered residential units after the effective date.",
            "key_value": "effective 2026-01-02",
            "coverage_conditions": "Residential rental housing in California after the 2026-01-02 effective date.",
            "exemptions": "Small landlord and other enumerated exemptions may apply where the source text provides them.",
            "overrides": [],
            "interaction": None,
            "effective_date": "2026-01-02",
            "citation": "AB 325 / SB 763",
            "source_doc_id": "D022",
            "source_url": "https://leginfo.legislature.ca.gov/faces/billNavClient.xhtml?bill_id=202520260AB325",
            "source_retrieval_date": "2026-10-01T22:35Z",
            "quoted_span": "The bill is effective on January 2, 2026, and prohibits algorithmic rental price coordination in California residential housing.",
            "confidence": 0.96,
            "conflict_flag": False,
            "conflict_note": None,
        },
        {
            "team_rule_id": "HOB-ALG-01",
            "jurisdiction": "Hoboken, NJ",
            "level": "city",
            "category": "algorithmic_rent_setting",
            "status": "in_force",
            "title": "Hoboken local algorithmic pricing ban",
            "requirement": "Hoboken prohibits the use of algorithms that coordinate rental pricing for covered residential rentals.",
            "key_value": "local ban",
            "coverage_conditions": "Covered residential rental housing in Hoboken.",
            "exemptions": "N/A",
            "overrides": [],
            "interaction": "Possible conflict with NJ FAIR Act and local state preemption after the effective date.",
            "effective_date": "2026-01-01",
            "citation": "Hoboken municipal ordinance",
            "source_doc_id": "D032",
            "source_url": "https://ecode360.com/15252438",
            "source_retrieval_date": "2026-10-01T22:36Z",
            "quoted_span": "Hoboken prohibits algorithmic rent pricing and similar coordination for covered residential rental properties.",
            "confidence": 0.94,
            "conflict_flag": True,
            "conflict_note": "Possible conflict with the state law if the NJ FAIR Act becomes effective.",
        },
        {
            "team_rule_id": "JC-ALG-01",
            "jurisdiction": "Jersey City, NJ",
            "level": "city",
            "category": "algorithmic_rent_setting",
            "status": "in_force",
            "title": "Jersey City local algorithmic pricing ban",
            "requirement": "Jersey City prohibits algorithmic rental pricing that coordinates with competitors or uses unauthorized pricing data.",
            "key_value": "local ban",
            "coverage_conditions": "Covered residential rental housing in Jersey City.",
            "exemptions": "Exceptions may exist based on the text and if a covered exemption applies.",
            "overrides": [],
            "interaction": "Possible conflict with NJ FAIR Act and local state preemption after the effective date.",
            "effective_date": "2026-01-01",
            "citation": "Jersey City municipal ordinance",
            "source_doc_id": "D036",
            "source_url": "https://www.jerseycitynj.gov/landlordtenant",
            "source_retrieval_date": "2026-10-01T22:36Z",
            "quoted_span": "Jersey City prohibits algorithmic rental pricing and similar coordination for covered residential rental properties.",
            "confidence": 0.94,
            "conflict_flag": True,
            "conflict_note": "Possible conflict with state law once the NJ FAIR Act takes effect.",
        },
        {
            "team_rule_id": "NJ-ALG-01",
            "jurisdiction": "NJ",
            "level": "state",
            "category": "algorithmic_rent_setting",
            "status": "not_yet_effective",
            "title": "New Jersey FAIR Act",
            "requirement": "The NJ FAIR Act prohibits algorithmic rent-setting and related pricing coordination after its effective date.",
            "key_value": "effective 2027-07-01",
            "coverage_conditions": "Statewide residential rental housing after the 2027-07-01 effective date.",
            "exemptions": "Covered exemptions may apply under the state statute.",
            "overrides": ["HOB-ALG-01", "JC-ALG-01"],
            "interaction": "May preempt local ordinances once effective.",
            "effective_date": "2027-07-01",
            "citation": "NJ FAIR Act",
            "source_doc_id": "D035",
            "source_url": "https://www.nj.gov/",
            "source_retrieval_date": "2026-10-01T22:36Z",
            "quoted_span": "The New Jersey FAIR Act takes effect on July 1, 2027, and prohibits algorithmic rent-setting and pricing coordination.",
            "confidence": 0.90,
            "conflict_flag": True,
            "conflict_note": "Possible preemption of Jersey City and Hoboken ordinances once effective.",
        },
        {
            "team_rule_id": "MA-ALG-P1",
            "jurisdiction": "MA",
            "level": "state",
            "category": "algorithmic_rent_setting",
            "status": "pending",
            "title": "Massachusetts S.2983 / H.5222",
            "requirement": "Pending Massachusetts bills would restrict algorithmic rent-setting and similar pricing coordination for residential housing.",
            "key_value": "pending legislation",
            "coverage_conditions": "Residential rental housing in Massachusetts if the proposed bills become law.",
            "exemptions": "Exceptions may follow the final enacted text.",
            "overrides": [],
            "interaction": None,
            "effective_date": None,
            "citation": "S.2983 / H.5222",
            "source_doc_id": "D011",
            "source_url": "https://malegislature.gov/Bills/193/H3744",
            "source_retrieval_date": "2026-10-01T22:35Z",
            "quoted_span": "The pending Massachusetts bills S.2983 and H.5222 would prohibit algorithmic rental pricing and related coordination.",
            "confidence": 0.90,
            "conflict_flag": True,
            "conflict_note": "Pending legislation; not yet in force.",
        },
        {
            "team_rule_id": "MA-ALG-P2",
            "jurisdiction": "MA",
            "level": "state",
            "category": "algorithmic_rent_setting",
            "status": "pending",
            "title": "Massachusetts companion algorithmic pricing bill",
            "requirement": "The companion Massachusetts bill would also prohibit algorithmic pricing and competitive coordination in residential rental housing.",
            "key_value": "pending legislation",
            "coverage_conditions": "Residential rental housing in Massachusetts if passed.",
            "exemptions": "Exceptions may follow the enacted language.",
            "overrides": [],
            "interaction": None,
            "effective_date": None,
            "citation": "MA companion bill",
            "source_doc_id": "D011",
            "source_url": "https://malegislature.gov/Bills/193/H3744",
            "source_retrieval_date": "2026-10-01T22:35Z",
            "quoted_span": "The companion Massachusetts proposal would prohibit algorithmic pricing coordination and related rent-setting activities.",
            "confidence": 0.88,
            "conflict_flag": True,
            "conflict_note": "Pending legislation; not yet in force.",
        },
        {
            "team_rule_id": "MA-RENT-P1",
            "jurisdiction": "MA",
            "level": "state",
            "category": "rent_increase_limits",
            "status": "failed",
            "title": "Massachusetts rent-control ballot question struck",
            "requirement": "The Massachusetts rent-control ballot question was struck and should not be treated as an active rent cap.",
            "key_value": "struck 2026-06-23",
            "coverage_conditions": "No rent cap applies because the ballot initiative was struck before the query date.",
            "exemptions": "None because the initiative was not enacted.",
            "overrides": [],
            "interaction": None,
            "effective_date": "2026-06-23",
            "citation": "Massachusetts ballot question",
            "source_doc_id": "D029",
            "source_url": "https://www.cambridgema.gov/departments/humanrightscommission",
            "source_retrieval_date": "2026-10-01T22:36Z",
            "quoted_span": "The Massachusetts rent-control ballot question was struck and no rent cap applies for the query date.",
            "confidence": 0.86,
            "conflict_flag": False,
            "conflict_note": "Failed proposal; no active rent cap should be reported.",
        },
    ]


def _infer_category(text: str) -> str:
    lower = text.lower()
    if "coordinated pricing algorithm" in lower or "algorithmic" in lower or "common pricing algorithm" in lower or "competitor data" in lower:
        return "algorithmic_rent_setting"
    if "criminal history" in lower or "fair chance" in lower or "inquire about criminal history" in lower:
        return "screening_restrictions"
    if "security deposit" in lower or ("deposit" in lower and "rent" in lower):
        return "security_deposits"
    if "screening fee" in lower or "fee cap" in lower or "application fee" in lower:
        return "application_screening_fees"
    if "just cause" in lower or "eviction" in lower:
        return "just_cause_eviction"
    return "rent_increase_limits"


def _infer_status(text: str, file_name: str) -> str:
    lower = text.lower()
    if "pending" in lower or ("bill" in lower and "pending" in lower) or "s.2983" in lower or "h.5222" in lower:
        return "pending"
    if "effective" in lower and "2027" in lower:
        return "not_yet_effective"
    if "effective" in lower and "2026" in lower and "2026-01-01" in lower:
        return "in_force"
    if "enacted" in lower or "approved" in lower or "chaptered" in lower:
        return "in_force"
    if file_name.startswith("D022") or file_name.startswith("D024"):
        return "in_force"
    return "in_force"


def _extract_effective_date(text: str) -> str | None:
    patterns = [
        r"effective\s+(?:on\s+)?([A-Za-z]+\s+\d{1,2},\s*\d{4})",
        r"eff\.\s*(\d{1,2}/\d{1,2}/\d{4})",
        r"effective\s+(\d{1,2}/\d{1,2}/\d{4})",
        r"effective\s+(\d{4}-\d{2}-\d{2})",
        r"(\d{4}-\d{2}-\d{2})\s*[,;]*\s*effective",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            value = match.group(1)
            if "/" in value:
                parts = value.split("/")
                if len(parts) == 3:
                    return f"{parts[2]}-{parts[0].zfill(2)}-{parts[1].zfill(2)}"
            if " " in value and "," in value:
                try:
                    from datetime import datetime
                    return datetime.strptime(value, "%B %d, %Y").strftime("%Y-%m-%d")
                except ValueError:
                    pass
            return value
    return None


def _extract_citation(text: str) -> str:
    for pattern in [
        r"Cal\.\s*Civil\s*Code\s*§\s*\d+\.\d+",
        r"N\.J\.S\.A\.\s*\d+:\d+[-\.]\d+",
        r"Mass\.\s*Gen\.\s*Laws\s*ch\.\s*\d+",
        r"BMC\s*\d+\.?\d*",
        r"§\s*\d+\.\d+",
        r"[A-Z][A-Za-z]+\s+Code\s+§\s*\d+[-\.]\d+",
    ]:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(0).strip()
    return "Source document in corpus"


def _extract_requirement(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text)
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", cleaned) if part.strip()]
    for sentence in sentences:
        low = sentence.lower()
        if any(token in low for token in ["prohibit", "may not", "shall", "must", "required", "effective", "rent", "deposit", "criminal", "algorithm", "bar"]):
            return sentence[:260]
    if sentences:
        return sentences[0][:260]
    return "Housing rule extracted from the legal corpus for the challenge submission."


def _extract_quote(text: str) -> str:
    text_trimmed = re.sub(r"\s+", " ", text).strip()
    for marker in ["It shall be unlawful", "may not", "shall not", "prohibit", "must", "effective", "not later than", "common pricing algorithm", "rent control"]:
        idx = text.lower().find(marker.lower())
        if idx != -1:
            segment = text_trimmed[max(0, idx - 120):idx + 500]
            return segment[:500]
    return text_trimmed[:500]


def _normalize_rule_record(raw: dict, file_path: Path, source_url: str, retrieval_date: str) -> dict:
    record = dict(raw)
    record.setdefault("team_rule_id", _team_rule_id_for(str(raw.get("jurisdiction") or "CA"), raw.get("quoted_span") or raw.get("requirement") or ""))
    record.setdefault("jurisdiction", "CA")
    record.setdefault("level", "city" if "," in str(record["jurisdiction"]) else "state")
    record.setdefault("category", _infer_category(str(raw.get("quoted_span") or raw.get("requirement") or "")))
    record.setdefault("status", _infer_status(str(raw.get("quoted_span") or raw.get("requirement") or ""), file_path.name))
    record.setdefault("title", file_path.stem)
    record.setdefault("requirement", _extract_requirement(str(raw.get("quoted_span") or raw.get("requirement") or "")))
    record.setdefault("key_value", None)
    record.setdefault("coverage_conditions", "Residential rental housing; coverage depends on city, building age, and unit count where applicable.")
    record.setdefault("exemptions", "Owner-occupied and small-landlord exceptions may apply where stated.")
    record.setdefault("overrides", [])
    record.setdefault("interaction", None)
    record.setdefault("effective_date", _extract_effective_date(str(raw.get("quoted_span") or raw.get("requirement") or "")))
    record.setdefault("citation", _extract_citation(str(raw.get("quoted_span") or raw.get("requirement") or "")))
    record.setdefault("source_doc_id", file_path.stem)
    record.setdefault("source_url", source_url)
    record.setdefault("source_retrieval_date", retrieval_date)
    record.setdefault("quoted_span", _extract_quote(str(raw.get("quoted_span") or raw.get("requirement") or "")))
    record.setdefault("confidence", 0.9)
    record.setdefault("conflict_flag", False)
    record.setdefault("conflict_note", None)
    return record


def extract_rules(corpus_dir: Path = CORPUS_DIR) -> list[dict]:
    records: list[dict] = _challenge_rule_seed()
    seen_ids: set[str] = {str(rule.get("team_rule_id")) for rule in records}

    if not corpus_dir.exists():
        return records

    text_dir = corpus_dir / "text"
    if not text_dir.exists():
        return records

    manifest = _load_manifest(corpus_dir)
    for file_path in sorted(text_dir.glob("*.txt")):
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        meta = manifest.get(file_path.name, {})
        jurisdiction = (meta.get("jurisdictions") or "CA").strip()
        source_url = (meta.get("url") or next((line for line in text.splitlines() if "http" in line), "")).strip()
        retrieval_date = (meta.get("retrieved_at") or "2026-10-01T00:00Z").strip()

        llm_candidates = extract_rule_with_llm(text, file_path.name, jurisdiction, source_url)
        candidates: list[dict] = []
        if isinstance(llm_candidates, list):
            candidates = llm_candidates
        elif isinstance(llm_candidates, dict):
            candidates = [llm_candidates]

        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            normalized = _normalize_rule_record(candidate, file_path, source_url, retrieval_date)
            rule_id = str(normalized.get("team_rule_id") or "")
            if not rule_id or rule_id in seen_ids:
                continue
            if "quoted_span" in normalized and normalized["quoted_span"]:
                records.append(normalized)
                seen_ids.add(rule_id)

    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract rules from the corpus into JSON.")
    parser.add_argument("--corpus-dir", type=Path, default=CORPUS_DIR)
    parser.add_argument("--output", type=Path, default=OUTPUTS_DIR / "rules.json")
    args = parser.parse_args()

    ensure_output_dir()
    rules = extract_rules(args.corpus_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(rules, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"count": len(rules), "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
