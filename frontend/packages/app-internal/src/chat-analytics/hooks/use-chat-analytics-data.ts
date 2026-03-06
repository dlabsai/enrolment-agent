import { useCallback, useEffect, useState } from "react";

import { useAuthenticatedApi } from "../../auth/hooks/use-authenticated-api";
import type { CustomTimeRange, TimeRangeValue } from "../../lib/time-range";
import type { ChatAnalyticsSummary } from "../../usage/types";
import {
    type ChatAnalyticsPlatform,
    fetchChatAnalyticsSummary,
} from "../lib/api";

interface UseChatAnalyticsDataResult {
    summary: ChatAnalyticsSummary | undefined;
    loading: boolean;
    hasLoaded: boolean;
    error: string | undefined;
    refresh: () => Promise<void>;
}

export const useChatAnalyticsData = (
    platform: ChatAnalyticsPlatform,
    timeRange: TimeRangeValue,
    customRange: CustomTimeRange,
): UseChatAnalyticsDataResult => {
    const api = useAuthenticatedApi();
    const [summary, setSummary] = useState<ChatAnalyticsSummary | undefined>();
    const [loading, setLoading] = useState(true);
    const [hasLoaded, setHasLoaded] = useState(false);
    const [error, setError] = useState<string | undefined>();

    const refresh = useCallback(async () => {
        setLoading(true);
        setError(undefined);
        try {
            const data = await fetchChatAnalyticsSummary(
                api,
                platform,
                timeRange,
                customRange,
            );
            setSummary(data);
        } catch (error_) {
            setError(
                error_ instanceof Error
                    ? error_.message
                    : "Failed to fetch analytics data",
            );
        } finally {
            setLoading(false);
            setHasLoaded(true);
        }
    }, [api, customRange, platform, timeRange]);

    useEffect(() => {
        void refresh();
    }, [refresh]);

    return { summary, loading, hasLoaded, error, refresh };
};
