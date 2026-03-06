import type { AuthenticatedApi } from "../../auth/hooks/use-authenticated-api";
import type {
    TraceDetail,
    TracePlatformFilter,
    TraceSummaryPage,
} from "../types";

interface FetchTraceIndexParams {
    aiOnly: boolean;
    limit: number;
    offset: number;
    platform: TracePlatformFilter;
    start?: string;
    end?: string;
}

export const fetchTraceIndex = async (
    api: AuthenticatedApi,
    params: FetchTraceIndexParams,
): Promise<TraceSummaryPage> => {
    const queryParams = new URLSearchParams({
        limit: String(params.limit),
        offset: String(params.offset),
        sort_by: "latest_start",
        descending: "true",
    });
    if (params.aiOnly) {
        queryParams.set("ai_only", "true");
    }
    if (params.platform !== "both") {
        queryParams.set("platform", params.platform);
    }
    if (params.start !== undefined) {
        queryParams.set("start", params.start);
    }
    if (params.end !== undefined) {
        queryParams.set("end", params.end);
    }
    const query = queryParams.toString();
    const path = query ? `/usage/trace-index?${query}` : "/usage/trace-index";
    return api.get<TraceSummaryPage>(path);
};

export const fetchTraceDetail = async (
    api: AuthenticatedApi,
    traceId: string,
): Promise<TraceDetail> => api.get<TraceDetail>(`/usage/trace/${traceId}`);

export const fetchTraceDetailByMessageId = async (
    api: AuthenticatedApi,
    messageId: string,
): Promise<TraceDetail> =>
    api.get<TraceDetail>(`/usage/trace-by-message/${messageId}`);
