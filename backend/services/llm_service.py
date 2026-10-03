import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[2]
AUDIT_LOG_PATH = PROJECT_ROOT / "audit.jsonl"


def llm_enabled() -> bool:
    enabled = os.getenv("USE_LLM_EXTRACTION", "false").strip().lower()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    return enabled in {"1", "true", "yes", "on"} and bool(api_key)


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
                    "You extract rules from rental housing legal text. Return valid JSON only. "
                    "Do not invent citations. Every rule must be grounded in the supplied text. "
                    "Use keys: team_rule_id, jurisdiction, level, category, status, title, requirement, "
                    "key_value, coverage_conditions, exemptions, overrides, interaction, effective_date, "
                    "citation, source_doc_id, source_url, quoted_span, confidence, conflict_flag, conflict_note. "
                    "If a fact is missing, set it to null or 'unknown' when required."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "temperature": 0.1,
    }


def extract_rule_with_llm(document_text: str, source_name: str, jurisdiction: str, source_url: str) -> dict[str, Any] | None:
    if not llm_enabled():
        return None

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")

    prompt = (
        "Extract one rule record from the legal text below. "
        "Return a JSON object with these keys. "
        "Do not include markdown fences. "
        f"Jurisdiction: {jurisdiction}\n"
        f"Source doc: {source_name}\n"
        f"Source URL: {source_url}\n\n"
        f"Text:\n{document_text[:12000]}"
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
        if isinstance(parsed, list):
            parsed = parsed[0] if parsed else {}
        if not isinstance(parsed, dict):
            raise ValueError("LLM response was not a JSON object")
        parsed.setdefault("team_rule_id", f"llm-{source_name}")
        parsed.setdefault("jurisdiction", jurisdiction)
        parsed.setdefault("level", "city" if "," in jurisdiction else "state")
        parsed.setdefault("status", "unknown")
        parsed.setdefault("source_doc_id", source_name)
        parsed.setdefault("source_url", source_url)
        parsed.setdefault("confidence", 0.9)
        _log_llm_call(source_name, payload, result)
        return parsed
    except Exception as exc:  # pragma: no cover - network/SDK failures are optional paths
        _log_llm_call(source_name, payload, None, str(exc))
        return None
