import json
from pathlib import Path

from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse

from backend.app.schemas import AddressQuery
from backend.core.config import settings
from backend.services.address_service import get_address_coverage, list_sample_addresses
from backend.services.rule_service import load_rules

app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description="API for the Rental Housing Law Navigator hackathon prototype.",
)


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok", "service": "rental-housing-law-navigator"}


@app.get("/")
def root() -> dict:
    return {
        "message": "Rental Housing Law Navigator API",
        "not_legal_advice": True,
        "as_of": settings.as_of_date,
    }


@app.get("/stats")
def stats() -> dict:
    rules = load_rules(settings.project_root / "outputs" / "rules.json")
    addresses = list_sample_addresses(limit=None)
    return {
        "rule_count": len(rules),
        "sample_address_count": len(addresses),
        "as_of": settings.as_of_date,
        "not_legal_advice": True,
    }


@app.get("/addresses")
def addresses(limit: int | None = Query(default=10, ge=1, le=100)) -> dict:
    return {
        "count": len(list_sample_addresses(limit=None)),
        "items": list_sample_addresses(limit=limit),
    }


@app.get("/rules")
def rules() -> dict:
    return {
        "count": len(load_rules(settings.project_root / "outputs" / "rules.json")),
        "items": load_rules(settings.project_root / "outputs" / "rules.json")[:20],
    }


@app.post("/analyze-address")
def analyze_address(payload: AddressQuery) -> dict:
    return get_address_coverage(payload.street_address, payload.as_of)


@app.get("/changes")
def changes(as_of: str | None = Query(default=None, description="Date used for legal tracking")) -> dict:
    changes_path = settings.project_root / "outputs" / "changes.json"
    payload = json.loads(changes_path.read_text(encoding="utf-8")) if changes_path.exists() else {"changes": []}
    response = {
        "as_of": as_of or settings.as_of_date,
        "not_legal_advice": True,
        "changes": payload if isinstance(payload, dict) else {"changes": payload},
    }
    return response


@app.get("/demo")
def demo_page() -> HTMLResponse:
    demo_path = settings.project_root / "frontend" / "index.html"
    if not demo_path.exists():
        html = """
        <html><body><h1>Rental Housing Law Navigator</h1><p>not legal advice</p></body></html>
        """
        return HTMLResponse(content=html)
    return HTMLResponse(content=demo_path.read_text(encoding="utf-8"))
