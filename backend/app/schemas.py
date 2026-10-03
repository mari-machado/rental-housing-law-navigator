from pydantic import BaseModel, Field


class AddressQuery(BaseModel):
    street_address: str = Field(..., min_length=3, description="Address to analyze")
    as_of: str = Field("2026-10-01", description="Date used for legal applicability")


class RuleSummary(BaseModel):
    team_rule_id: str
    jurisdiction: str
    title: str
    status: str
    citation: str
    source_url: str
