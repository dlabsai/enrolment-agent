export interface TraceSummary {
    trace_id: string;
    started_at: string | null;
    duration_ms: number | null;
    span_count: number;
    root_span_name: string | null;
    model: string | null;
    is_error: boolean;
    is_public: boolean | null;
    conversation_id: string | null;
    is_ai: boolean;
}

export interface TraceSummaryPage {
    items: TraceSummary[];
    total: number;
}

export type TracePlatformFilter = "both" | "internal" | "public";

export interface TraceSpan {
    span_id: string;
    parent_span_id: string | null;
    name: string;
    kind: string | null;
    status_code: string | null;
    status_message: string | null;
    start_time: string | null;
    end_time: string | null;
    duration_ms: number | null;
    attributes: Record<string, unknown> | null;
    events: Record<string, unknown>[] | null;
    links: Record<string, unknown>[] | null;
    resource: Record<string, unknown> | null;
    scope: Record<string, unknown> | null;
}

export interface TraceDetail {
    trace_id: string;
    started_at: string | null;
    duration_ms: number | null;
    span_count: number;
    is_public: boolean | null;
    conversation_id: string | null;
    spans: TraceSpan[];
}
