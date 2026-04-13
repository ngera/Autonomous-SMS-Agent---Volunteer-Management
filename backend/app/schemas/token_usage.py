from datetime import datetime

from pydantic import BaseModel


class TokenUsageSummary(BaseModel):
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    total_requests: int
    estimated_cost_usd: float


class TokenUsageBySource(BaseModel):
    source: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    request_count: int


class TokenUsageByModel(BaseModel):
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    request_count: int


class TokenUsageByDay(BaseModel):
    date: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    request_count: int


class TokenUsageByVolunteer(BaseModel):
    contact_id: str | None
    contact_phone: str | None
    contact_name: str | None
    input_tokens: int
    output_tokens: int
    total_tokens: int
    request_count: int
    estimated_cost_usd: float


class TokenUsageByTool(BaseModel):
    tool_name: str
    call_count: int
    request_count: int


class TokenUsageDetail(BaseModel):
    id: str
    source: str
    model: str
    input_tokens: int
    output_tokens: int
    contact_phone: str | None
    contact_name: str | None
    tool_names: list[str]
    created_at: datetime


class TokenUsageDashboard(BaseModel):
    summary: TokenUsageSummary
    by_source: list[TokenUsageBySource]
    by_model: list[TokenUsageByModel]
    daily: list[TokenUsageByDay]
    by_volunteer: list[TokenUsageByVolunteer]
    by_tool: list[TokenUsageByTool]
    recent: list[TokenUsageDetail]
