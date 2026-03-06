import { fetchTraceDetail } from "../lib/api";
import type { TraceDetail } from "../types";
import { useTraceDetailLoader } from "./use-trace-detail-loader";

interface UseTraceDetailResult {
    detail: TraceDetail | undefined;
    loading: boolean;
    error: string | undefined;
    refresh: () => Promise<void>;
}

export const useTraceDetail = (
    traceId: string | undefined,
): UseTraceDetailResult => useTraceDetailLoader(traceId, fetchTraceDetail);
