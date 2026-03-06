import type { EvalRunStatusEvent } from "../types";

export const parseTestCaseInput = (value: string): string[] =>
    value
        .split(",")
        .map((entry) => entry.trim())
        .filter((entry) => entry !== "");

export const parsePositiveInt = (value: string, fallback: number): number => {
    const parsed = Number.parseInt(value, 10);
    if (Number.isNaN(parsed) || parsed < 1) {
        return fallback;
    }
    return parsed;
};

export const parsePassThreshold = (value: string, fallback: number): number => {
    const parsed = Number.parseFloat(value);
    if (Number.isNaN(parsed) || parsed <= 0 || parsed > 1) {
        return fallback;
    }
    return parsed;
};

export const resolveRunStatusLabel = (
    status: EvalRunStatusEvent["status"] | "idle",
    exitCode?: number,
): string => {
    if (status === "start") {
        return "Starting";
    }
    if (status === "complete") {
        return exitCode === undefined
            ? "Completed"
            : `Completed (exit ${exitCode})`;
    }
    if (status === "error") {
        return exitCode === undefined ? "Failed" : `Failed (exit ${exitCode})`;
    }
    if (status === "cancelled") {
        return "Cancelled";
    }
    return "Idle";
};

export const resolveRunStatusVariant = (
    status: EvalRunStatusEvent["status"] | "idle",
): "secondary" | "destructive" | "outline" => {
    if (status === "error") {
        return "destructive";
    }
    if (status === "start") {
        return "secondary";
    }
    if (status === "complete") {
        return "outline";
    }
    if (status === "cancelled") {
        return "secondary";
    }
    return "outline";
};
