import json
from pathlib import Path
from typing import Any


def load_json(path: str | Path) -> Any:
    path = Path(path)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_rules(rules_path: str | Path) -> list[dict[str, Any]]:
    data = load_json(rules_path)
    if isinstance(data, list):
        return data
    return data.get("rules", []) if isinstance(data, dict) else []


def get_rule_count(rules_path: str | Path) -> int:
    return len(load_rules(rules_path))
