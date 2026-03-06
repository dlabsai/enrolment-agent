from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import Query
from pydantic import BaseModel, ConfigDict

_from_attributes = ConfigDict(from_attributes=True)


class MessageOut(BaseModel):
    message: str


class PageOut[M](BaseModel):
    items: list[M]
    total: int


class PaginationParams(BaseModel):
    limit: Annotated[int, Query(ge=0)] = 10
    offset: Annotated[int, Query(ge=0)] = 0
    sort_by: Annotated[str, Query()] = "created_at"
    descending: Annotated[bool, Query()] = True


class BaseFilters(BaseModel):
    search: Annotated[str | None, Query()] = None
    id: Annotated[str | None, Query()] = None


# Authentication schemas
class UserBase(BaseModel):
    email: str
    name: str


class UserCreate(UserBase):
    password: str
    confirm_password: str
    registration_token: str


class UserOut(UserBase):
    id: UUID
    is_active: bool
    role: str
    created_at: datetime
    updated_at: datetime

    model_config = _from_attributes


class UserLogin(BaseModel):
    email: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105


class TokenData(BaseModel):
    user_id: str | None = None


class GlobalFeedbackItem(BaseModel):
    id: UUID
    type: str
    rating: str
    text: str | None = None
    user_name: str
    is_current_user: bool
    created_at: datetime
    conversation_id: UUID
    conversation_title: str | None = None
    message_id: UUID | None = None
    message_preview: str | None = None


class GlobalFeedbackResponse(BaseModel):
    feedback_items: list[GlobalFeedbackItem]


class UsageTraceBasicOut(BaseModel):
    created_at: datetime
    model: str
    prompt_tokens: int | None
    completion_tokens: int | None
    cost: float | None
    duration: float | None
    is_error: bool
    is_public: bool | None


class UsageDailyOut(BaseModel):
    date: datetime
    requests: int
    tokens: int
    cost: float
    embedding_requests: int
    embedding_tokens: int
    embedding_cost: float
    errors: int
    avg_duration: float


class UsageModelOut(BaseModel):
    model: str
    requests: int
    tokens: int
    cost: float


class UsageSummaryOut(BaseModel):
    total_requests: int
    total_tokens: int
    total_cost: float
    total_embedding_requests: int
    total_embedding_tokens: int
    total_embedding_cost: float
    total_embedding_avg_duration: float
    total_errors: int
    avg_duration: float


class UsageOverviewOut(BaseModel):
    summary: UsageSummaryOut
    daily: list[UsageDailyOut]
    models: list[UsageModelOut]
    latest_traces: list[UsageTraceBasicOut]


class EvalReportSummaryOut(BaseModel):
    id: str
    name: str
    generated_at: datetime
    repeats: int | None = None
    concurrency: int | None = None
    filename: str
    size_bytes: int


class EvalReportDetailOut(BaseModel):
    id: str
    name: str
    generated_at: datetime
    repeats: int | None = None
    concurrency: int | None = None
    filename: str
    size_bytes: int
    content: str


class EvalTestCasesOut(BaseModel):
    suite: str
    cases: list[str]


class EvalRunLogFileOut(BaseModel):
    id: str
    filename: str
    size_bytes: int
    content: str


class EvalRunRequest(BaseModel):
    suite: str
    repeat: int = 1
    max_concurrency: int = 5
    test_cases: str | None = None
    pass_threshold: float = 0.9
    chatbot_model: str | None = None
    guardrail_model: str | None = None
    extractor_model: str | None = None
    evaluation_model: str | None = None
    search_model: str | None = None


class TraceSpanOut(BaseModel):
    span_id: str
    parent_span_id: str | None
    name: str
    kind: str | None
    status_code: str | None
    status_message: str | None
    start_time: datetime | None
    end_time: datetime | None
    duration_ms: float | None
    attributes: dict[str, Any] | None
    events: list[dict[str, Any]] | None
    links: list[dict[str, Any]] | None
    resource: dict[str, Any] | None
    scope: dict[str, Any] | None


class TraceDetailOut(BaseModel):
    trace_id: str
    started_at: datetime | None
    duration_ms: float | None
    span_count: int
    is_public: bool | None
    conversation_id: UUID | None
    spans: list[TraceSpanOut]


class TraceSummaryOut(BaseModel):
    trace_id: str
    started_at: datetime | None
    duration_ms: float | None
    span_count: int
    root_span_name: str | None
    model: str | None
    is_error: bool
    is_public: bool | None
    conversation_id: UUID | None
    is_ai: bool


class ConversationAnalyticsDailyOut(BaseModel):
    date: datetime
    conversations: int
    messages: int
    avg_messages_per_conversation: float
    single_message_rate: float


class ConversationAnalyticsBucketOut(BaseModel):
    label: str
    conversations: int


class ConversationAnalyticsHourlyOut(BaseModel):
    hour: int
    messages: int


class ConversationAnalyticsResponseTimeBucketOut(BaseModel):
    label: str
    responses: int


class ConversationAnalyticsStatsOut(BaseModel):
    min: float | None
    p50: float | None
    median: float | None
    avg: float | None
    p75: float | None
    p90: float | None
    p95: float | None
    p99: float | None
    max: float | None


class ConversationAnalyticsSummaryOut(BaseModel):
    total_conversations: int
    total_messages: int
    avg_messages_per_conversation: float
    single_message_rate: float
    daily: list[ConversationAnalyticsDailyOut]
    length_buckets: list[ConversationAnalyticsBucketOut]
    hourly_activity: list[ConversationAnalyticsHourlyOut]
    length_stats: ConversationAnalyticsStatsOut | None
    response_time_buckets: list[ConversationAnalyticsResponseTimeBucketOut]
    response_time_stats: ConversationAnalyticsStatsOut | None


class PublicUsageDailyOut(BaseModel):
    date: datetime
    conversations: int
    messages: int
    avg_messages_per_conversation: float
    drop_off_rate: float
    leads: int


class PublicUsageBucketOut(BaseModel):
    label: str
    conversations: int


class PublicUsageHourlyOut(BaseModel):
    hour: int
    messages: int


class PublicUsageSummaryOut(BaseModel):
    total_conversations: int
    total_messages: int
    avg_messages_per_conversation: float
    drop_off_rate: float
    total_leads: int
    lead_capture_rate: float
    daily: list[PublicUsageDailyOut]
    depth_buckets: list[PublicUsageBucketOut]
    hourly_activity: list[PublicUsageHourlyOut]
