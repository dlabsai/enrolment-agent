import { useCallback, useEffect, useState } from "react";

import { useAuthenticatedApi } from "../../auth/hooks/use-authenticated-api";
import type { CustomTimeRange, TimeRangeValue } from "../../lib/time-range";
import { fetchPublicUsageSummary } from "../../public-analytics/lib/api";
import type { PublicUsageSummary } from "../types";

interface UsePublicUsageDataResult {
    summary: PublicUsageSummary | undefined;
    loading: boolean;
    hasLoaded: boolean;
    error: string | undefined;
    refresh: () => Promise<void>;
}

export const usePublicUsageData = (
    timeRange: TimeRangeValue,
    customRange: CustomTimeRange,
): UsePublicUsageDataResult => {
    const api = useAuthenticatedApi();
    const [summary, setSummary] = useState<PublicUsageSummary | undefined>();
    const [loading, setLoading] = useState(true);
    const [hasLoaded, setHasLoaded] = useState(false);
    const [error, setError] = useState<string | undefined>();

    const refresh = useCallback(async () => {
        setLoading(true);
        setError(undefined);
        try {
            const data = await fetchPublicUsageSummary(
                api,
                timeRange,
                customRange,
            );
            setSummary(data);
        } catch (error_) {
            setError(
                error_ instanceof Error
                    ? error_.message
                    : "Failed to fetch public usage data",
            );
        } finally {
            setLoading(false);
            setHasLoaded(true);
        }
    }, [api, customRange, timeRange]);

    useEffect(() => {
        void refresh();
    }, [refresh]);

    return { summary, loading, hasLoaded, error, refresh };
};
