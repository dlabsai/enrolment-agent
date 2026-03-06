import type { TimeRangeValue } from "./time-range";

export const isHourlyTimeRange = (timeRange: TimeRangeValue): boolean =>
    timeRange === "24h";

export const formatTimeSeriesTick = (
    value: string,
    timeRange: TimeRangeValue,
): string => {
    const date = new Date(value);
    if (isHourlyTimeRange(timeRange)) {
        return date.toLocaleTimeString("en-US", { hour: "numeric" });
    }
    return date.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
    });
};

export const formatTimeSeriesTooltipLabel = (
    value: string,
    timeRange: TimeRangeValue,
): string => {
    const date = new Date(value);
    if (isHourlyTimeRange(timeRange)) {
        return date.toLocaleString("en-US", {
            month: "short",
            day: "numeric",
            hour: "numeric",
        });
    }
    return date.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
    });
};
