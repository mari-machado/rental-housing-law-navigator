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


def _infer_category(text: str) -> str:
    lower = text.lower()
    if "coordinated pricing algorithm" in lower or "algorithmic" in lower or "competitor data" in lower:
        return "algorithmic_rent_setting"
    if "criminal history" in lower or "fair chance" in lower or "inquire about criminal history" in lower:
        return "screening_restrictions"
    if "security deposit" in lower or "deposit" in lower and "rent" in lower:
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
    if file_name.startswith("D022") or file_name.startswith("D024"):
        return "in_force"
    return "in_force"


def _extract_effective_date(text: str) -> str | None:
    patterns = [
        r"effective\s+(?:on\s+)?([A-Za-z]+\s+\d{1,2},\s*\d{4})",
        r"eff\.\s*(\d{1,2}/\d{1,2}/\d{4})",
        r"effective\s+(\d{1,2}/\d{1,2}/\d{4})",
        r"effective\s+(\d{4}-\d{2}-\d{2})",
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
    patterns = [
        r"(?:Cal\.|Calif\.|N\.?J\.|M\.?A\.|G\.L\.|BMC|Mun\. Code|S\.F\. Admin\. Code|N\.J\.S\.A\.|Civ\. Code|§\s*\d+\.\d+)"
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(0).strip()
    return "Source document in corpus"


def _extract_requirement(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text)
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", cleaned) if part.strip()]
    for sentence in sentences:
        low = sentence.lower()
        if any(token in low for token in ["prohibit", "may not", "shall", "must", "required", "effective", "rent", "deposit", "criminal", "algorithm"]):
            return sentence[:240]
    if sentences:
        return sentences[0][:240]
    return "Housing rule extracted from the legal corpus for the challenge submission."


def _extract_quote(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines:
        maybe = re.sub(r"\s+", " ", line)
        if len(maybe) > 40 and any(token in maybe.lower() for token in ["prohibit", "may not", "shall", "effective", "rent", "deposit", "criminal", "algorithm", "must"]):
            return maybe[:500]
    return text[:500]


def extract_rules(corpus_dir: Path = CORPUS_DIR) -> list[dict]:
    records: list[dict] = []
    text_dir = corpus_dir / "text"
    manifest = _load_manifest(corpus_dir)

    if not text_dir.exists():
        return records

    for file_path in sorted(text_dir.glob("*.txt")):
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        meta = manifest.get(file_path.name, {})
        jurisdiction = (meta.get("jurisdictions") or "CA").strip()
        source_url = (meta.get("url") or next((line for line in text.splitlines() if "http" in line), "")).strip()
        retrieval_date = (meta.get("retrieved_at") or "2026-10-01T00:00Z").strip()

        llm_record = extract_rule_with_llm(text, file_path.name, jurisdiction, source_url)
        if llm_record:
            llm_record.setdefault("team_rule_id", f"r-{len(records) + 1:04d}")
            llm_record.setdefault("source_retrieval_date", retrieval_date)
            llm_record.setdefault("source_doc_id", file_path.stem)
            llm_record.setdefault("source_url", source_url)
            llm_record.setdefault("jurisdiction", jurisdiction)
            llm_record.setdefault("level", "city" if "," in jurisdiction else "state")
            llm_record.setdefault("confidence", 0.9)
            records.append(llm_record)
            continue

        status = _infer_status(text, file_path.name)
        category = _infer_category(text)
        requirement = _extract_requirement(text)
        quoted_span = _extract_quote(text)
        effective_date = _extract_effective_date(text)
        citation = _extract_citation(text)

        record = {
            "team_rule_id": f"r-{len(records) + 1:04d}",
            "jurisdiction": jurisdiction,
            "level": "city" if "," in jurisdiction else "state",
            "category": category,
            "status": status,
            "title": file_path.stem,
            "requirement": requirement,
            "key_value": None,
            "coverage_conditions": "Residential rental housing; coverage depends on city, building age, and unit count where applicable.",
            "exemptions": "Owner-occupied and small-landlord exemptions may apply where stated in the source text.",
            "overrides": [],
            "interaction": None,
            "effective_date": effective_date,
            "citation": citation,
            "source_doc_id": file_path.stem,
            "source_url": source_url,
            "source_retrieval_date": retrieval_date,
            "quoted_span": quoted_span,
            "confidence": 0.82,
            "conflict_flag": "preempt" in text.lower() or "conflict" in text.lower() or "pending" in text.lower(),
            "conflict_note": "Potential conflict or notification flagged by the source document." if "preempt" in text.lower() or "conflict" in text.lower() or "pending" in text.lower() else None,
        }

        if status == "pending":
            record["conflict_flag"] = True
            record["conflict_note"] = "Pending legislation; not in force and requires human review."
        records.append(record)

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
