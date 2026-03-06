import { formatDurationMs } from "../lib/trace-utils";

export const getNumericAttribute = (
    attributes: Record<string, unknown>,
    key: string,
): number | undefined => {
    const value = attributes[key];
    if (typeof value === "number") {
        return value;
    }
    if (typeof value === "string") {
        const parsed = Number(value);
        return Number.isFinite(parsed) ? parsed : undefined;
    }
    return undefined;
};

export const formatNumeric = (value: number | undefined): string => {
    if (value === undefined) {
        return "-";
    }
    if (Number.isInteger(value)) {
        return value.toLocaleString("en-US");
    }
    return value.toLocaleString("en-US", { maximumFractionDigits: 4 });
};

export const formatCost = (value: number | undefined): string => {
    if (value === undefined) {
        return "-";
    }
    return value.toLocaleString("en-US", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 6,
    });
};

export const formatOffsetMs = (value: number | undefined): string => {
    if (value === undefined) {
        return "-";
    }
    if (value < 1000) {
        return `${Math.round(value)}ms`;
    }
    return `${(value / 1000).toFixed(2)}s`;
};

export const formatOffset = (value: number | undefined): string => {
    if (value === undefined) {
        return "-";
    }
    if (value <= 0) {
        return "0ms";
    }
    return formatDurationMs(value);
};

export const formatTimestampWithSeconds = (
    value: string | null | undefined,
): string => {
    if (value === null || value === undefined || value.trim() === "") {
        return "-";
    }
    return new Date(value).toLocaleString("en-US", {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
    });
};
