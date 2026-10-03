import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[2]
AUDIT_LOG_PATH = PROJECT_ROOT / "audit.jsonl"
REQUIRED_FIELDS = {
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


def llm_enabled() -> bool:
    enabled = os.getenv("USE_LLM_EXTRACTION")
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return False
    if enabled is None:
        return True
    return enabled.strip().lower() in {"1", "true", "yes", "on"}


def _log_llm_call(source: str, payload: dict[str, Any], response: dict[str, Any] | None = None, error: str | None = None) -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "payload": payload,
        "response": response,
        "error": error,
    }
    with AUDIT_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _build_openai_payload(prompt: str, model: str) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are extracting rental-housing legal rules from a corpus. "
                    "Return valid JSON only, as a list of rule objects. "
                    "Each rule must be grounded in the supplied text. "
                    "Use these keys: team_rule_id, jurisdiction, level, category, status, title, requirement, "
                    "key_value, coverage_conditions, exemptions, overrides, interaction, effective_date, "
                    "citation, source_doc_id, source_url, quoted_span, confidence, conflict_flag, conflict_note. "
                    "If a fact is unknown, use null. "
                    "Do not invent citations or dates. "
                    "The quoted_span must match a verbatim sentence or clause from the source text."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "temperature": 0.1,
    }


def _validate_rule_record(record: dict[str, Any]) -> bool:
    if not isinstance(record, dict):
        return False
    if not REQUIRED_FIELDS.issubset(record.keys()):
        return False
    quoted = str(record.get("quoted_span") or "").strip()
    return len(quoted) >= 20 and bool(str(record.get("source_url") or "").strip())


def extract_rule_with_llm(document_text: str, source_name: str, jurisdiction: str, source_url: str) -> list[dict[str, Any]] | dict[str, Any] | None:
    if not llm_enabled():
        return None

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")

    prompt = (
        "Extract all rule records from the legal text below. "
        "Return a JSON array of objects, one object per rule. "
        "Use the exact document text to support each rule. "
        "Do not include markdown fences. \n"
        f"Jurisdiction: {jurisdiction}\n"
        f"Source doc: {source_name}\n"
        f"Source URL: {source_url}\n\n"
        f"Text:\n{document_text[:15000]}"
    )

    payload = _build_openai_payload(prompt, model)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        if isinstance(parsed, dict) and "rules" in parsed:
            parsed = parsed["rules"]
        if not isinstance(parsed, list):
            parsed = [parsed] if isinstance(parsed, dict) else []

        valid: list[dict[str, Any]] = []
        for item in parsed:
            if isinstance(item, dict) and _validate_rule_record(item):
                item.setdefault("team_rule_id", f"llm-{source_name}")
                item.setdefault("jurisdiction", jurisdiction)
                item.setdefault("level", "city" if "," in jurisdiction else "state")
                item.setdefault("status", "unknown")
                item.setdefault("source_doc_id", source_name)
                item.setdefault("source_url", source_url)
                item.setdefault("confidence", 0.9)
                valid.append(item)

        _log_llm_call(source_name, payload, result)
        return valid
    except Exception as exc:  # pragma: no cover - network/SDK failures are optional paths
        _log_llm_call(source_name, payload, None, str(exc))
        return []
