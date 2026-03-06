import type { AuthenticatedApi } from "../../auth/hooks/use-authenticated-api";
import {
    type CustomTimeRange,
    getTimeRangeQueryParams,
    type TimeRangeValue,
} from "../../lib/time-range";
import type { ChatAnalyticsSummary } from "../../usage/types";

export type ChatAnalyticsPlatform = "both" | "internal" | "public";

export const fetchChatAnalyticsSummary = async (
    api: AuthenticatedApi,
    platform: ChatAnalyticsPlatform,
    timeRange: TimeRangeValue,
    customRange: CustomTimeRange,
): Promise<ChatAnalyticsSummary> => {
    const params = new URLSearchParams(
        getTimeRangeQueryParams(timeRange, new Date(), customRange),
    );
    if (platform !== "both") {
        params.set("platform", platform);
    }
    return api.get<ChatAnalyticsSummary>(
        `/analytics/conversations?${params.toString()}`,
    );
};
