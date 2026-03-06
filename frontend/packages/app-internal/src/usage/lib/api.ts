import type { AuthenticatedApi } from "../../auth/hooks/use-authenticated-api";
import {
    type CustomTimeRange,
    getTimeRangeQueryParams,
    type TimeRangeValue,
} from "../../lib/time-range";
import type { UsageOverviewApi } from "../types";

export type UsagePlatformFilter = "both" | "internal" | "public";

interface UsageOverviewParams {
    platform: UsagePlatformFilter;
    timeRange: TimeRangeValue;
    customRange: CustomTimeRange;
    modelFilters?: string[];
    referenceDate?: Date;
}

export const fetchUsageOverview = async (
    api: AuthenticatedApi,
    {
        platform,
        timeRange,
        customRange,
        modelFilters,
        referenceDate,
    }: UsageOverviewParams,
): Promise<UsageOverviewApi> => {
    const params = new URLSearchParams(
        getTimeRangeQueryParams(timeRange, referenceDate, customRange),
    );

    if (platform !== "both") {
        params.set("platform", platform);
    }

    if (modelFilters !== undefined && modelFilters.length > 0) {
        for (const modelFilter of modelFilters) {
            params.append("models", modelFilter);
        }
    }

    const query = params.toString();
    return api.get<UsageOverviewApi>(
        query ? `/usage/summary?${query}` : "/usage/summary",
    );
};
