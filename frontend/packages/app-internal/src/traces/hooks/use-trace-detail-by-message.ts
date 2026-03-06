import { fetchTraceDetailByMessageId } from "../lib/api";
import type { TraceDetail } from "../types";
import { useTraceDetailLoader } from "./use-trace-detail-loader";

interface UseTraceDetailByMessageResult {
    detail: TraceDetail | undefined;
    loading: boolean;
    error: string | undefined;
    refresh: () => Promise<void>;
}

export const useTraceDetailByMessage = (
    messageId: string | undefined,
): UseTraceDetailByMessageResult =>
    useTraceDetailLoader(messageId, fetchTraceDetailByMessageId, {
        clearDetailOnError: true,
    });
