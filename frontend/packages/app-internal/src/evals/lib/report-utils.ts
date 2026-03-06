import type { EvalReportDetail, EvalReportSummary } from "../types";

export const formatTimestamp = (value: string): string =>
    new Date(value).toLocaleString("en-US", {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    });

export const formatOptionalNumber = (
    value: number | null | undefined,
): string => (value === null || value === undefined ? "-" : value.toString());

export const formatBytes = (bytes: number): string => {
    if (bytes < 1024) {
        return `${bytes} B`;
    }
    const kb = bytes / 1024;
    if (kb < 1024) {
        return `${kb.toFixed(1)} KB`;
    }
    const mb = kb / 1024;
    return `${mb.toFixed(1)} MB`;
};

export const formatModelValue = (value: string | undefined): string =>
    value === undefined || value === "" ? "-" : value;

export const formatReportMeta = (
    report: EvalReportSummary | EvalReportDetail,
): string =>
    `Generated ${formatTimestamp(report.generatedAt)} · Repeats ${formatOptionalNumber(
        report.repeats,
    )} · Concurrency ${formatOptionalNumber(
        report.concurrency,
    )} · ${formatBytes(report.sizeBytes)}`;

interface EvalCaseSummary {
    caseName: string;
    runs: number | undefined;
    passRate: number | undefined;
    runtimeErrorRate: number | undefined;
    durationMin: number | undefined;
    durationMedian: number | undefined;
    durationMax: number | undefined;
    assertions: string;
}

interface EvalCompareRow {
    caseName: string;
    left?: EvalCaseSummary;
    right?: EvalCaseSummary;
}

interface EvalModelConfig {
    role: string;
    model: string;
}

type EvalModelRoleKey = "chatbot" | "guardrails" | "search";

interface EvalReportSummaryMetrics {
    passRateAverage: number | undefined;
    durationMedianAverage: number | undefined;
}

interface EvalModelCompareRow {
    role: string;
    left?: EvalModelConfig;
    right?: EvalModelConfig;
}

const parsePercentValue = (value: string): number | undefined => {
    const cleaned = value.replaceAll("%", "").trim();
    if (cleaned === "" || cleaned === "-") {
        return undefined;
    }
    const parsed = Number.parseFloat(cleaned);
    if (Number.isNaN(parsed)) {
        return undefined;
    }
    return parsed / 100;
};

const parseDurationValue = (
    value: string,
): {
    min: number | undefined;
    median: number | undefined;
    max: number | undefined;
} => {
    const parts = value
        .split("/")
        .map((part) => part.trim())
        .filter((part) => part !== "");
    if (parts.length < 3) {
        return {
            min: undefined,
            median: undefined,
            max: undefined,
        };
    }
    const [minValue, medianValue, maxValue] = parts.map((part) => {
        const cleaned = part.replace(/s$/iu, "").trim();
        const parsed = Number.parseFloat(cleaned);
        return Number.isNaN(parsed) ? undefined : parsed;
    });
    return {
        min: minValue,
        median: medianValue,
        max: maxValue,
    };
};

export const parseSummaryTable = (content: string): EvalCaseSummary[] => {
    const summaryMatch =
        /## Summary\s*(?<summary>[\s\S]*?)(?=\n## |\n### |$)/u.exec(content);
    const summaryText = summaryMatch?.groups?.summary;
    if (summaryText === undefined) {
        return [];
    }
    const lines = summaryText
        .split("\n")
        .map((line) => line.trim())
        .filter((line) => line !== "");
    const rows: EvalCaseSummary[] = [];

    for (const line of lines) {
        if (line.startsWith("|")) {
            const columns = line
                .split("|")
                .map((part) => part.trim())
                .filter(
                    (part, index, array) =>
                        part !== "" &&
                        index !== 0 &&
                        index !== array.length - 1,
                );
            if (columns.length >= 5) {
                const [
                    caseName,
                    runsValue,
                    passRateValue,
                    runtimeErrorValue,
                    durationValue,
                ] = columns;
                const assertionsValue = columns.length > 5 ? columns[5] : "";
                const isSeparator = caseName.replaceAll("-", "") === "";
                if (caseName !== "Case" && !isSeparator) {
                    const runsParsed = Number.parseInt(runsValue, 10);
                    const duration = parseDurationValue(durationValue);
                    rows.push({
                        caseName,
                        runs: Number.isNaN(runsParsed) ? undefined : runsParsed,
                        passRate: parsePercentValue(passRateValue),
                        runtimeErrorRate: parsePercentValue(runtimeErrorValue),
                        durationMin: duration.min,
                        durationMedian: duration.median,
                        durationMax: duration.max,
                        assertions: assertionsValue,
                    });
                }
            }
        }
    }

    return rows;
};

const resolveModelRoleKey = (role: string): EvalModelRoleKey | undefined => {
    const normalized = role.trim().toLowerCase();
    if (normalized.includes("chatbot")) {
        return "chatbot";
    }
    if (normalized.includes("guardrail")) {
        return "guardrails";
    }
    if (normalized.includes("search")) {
        return "search";
    }
    return undefined;
};

export const parseModelConfigurations = (
    content: string,
): EvalModelConfig[] => {
    const modelMatch =
        /## Model Configurations\s*(?<models>[\s\S]*?)(?=\n## |\n### |$)/u.exec(
            content,
        );
    const modelText = modelMatch?.groups?.models;
    if (modelText === undefined) {
        return [];
    }
    const lines = modelText
        .split("\n")
        .map((line) => line.trim())
        .filter((line) => line !== "");
    const rows: EvalModelConfig[] = [];
    for (const line of lines) {
        if (line.startsWith("|")) {
            const columns = line
                .split("|")
                .map((part) => part.trim())
                .filter(
                    (part, index, array) =>
                        part !== "" &&
                        index !== 0 &&
                        index !== array.length - 1,
                );
            if (columns.length >= 2) {
                const [roleValue, modelValue] = columns;
                const isSeparator = roleValue.replaceAll("-", "") === "";
                if (roleValue !== "Role" && !isSeparator) {
                    rows.push({
                        role: roleValue,
                        model: modelValue.replaceAll("`", "").trim(),
                    });
                }
            }
        }
    }
    return rows;
};

export const buildReportSummaryMetrics = (
    content: string,
): EvalReportSummaryMetrics => {
    const summaries = parseSummaryTable(content);
    const passRates = summaries
        .map((summary) => summary.passRate)
        .filter((value): value is number => value !== undefined);
    const durationMedians = summaries
        .map((summary) => summary.durationMedian)
        .filter((value): value is number => value !== undefined);
    const passRateAverage =
        passRates.length > 0
            ? passRates.reduce((total, value) => total + value, 0) /
              passRates.length
            : undefined;
    const durationMedianAverage =
        durationMedians.length > 0
            ? durationMedians.reduce((total, value) => total + value, 0) /
              durationMedians.length
            : undefined;
    return {
        passRateAverage,
        durationMedianAverage,
    };
};

export const buildModelRoleMap = (
    content: string,
): Partial<Record<EvalModelRoleKey, string>> => {
    const modelConfigs = parseModelConfigurations(content);
    const roles: Partial<Record<EvalModelRoleKey, string>> = {};
    for (const config of modelConfigs) {
        const roleKey = resolveModelRoleKey(config.role);
        if (roleKey !== undefined) {
            roles[roleKey] = config.model;
        }
    }
    return roles;
};

export const buildCompareRows = (
    left: EvalCaseSummary[],
    right: EvalCaseSummary[],
): EvalCompareRow[] => {
    const rightMap = new Map(
        right.map((summary) => [summary.caseName, summary]),
    );
    const leftMap = new Map(left.map((summary) => [summary.caseName, summary]));
    const rows: EvalCompareRow[] = left.map((summary) => ({
        caseName: summary.caseName,
        left: summary,
        right: rightMap.get(summary.caseName),
    }));

    for (const summary of right) {
        if (!leftMap.has(summary.caseName)) {
            rows.push({
                caseName: summary.caseName,
                right: summary,
            });
        }
    }

    return rows;
};

export const buildModelCompareRows = (
    left: EvalModelConfig[],
    right: EvalModelConfig[],
): EvalModelCompareRow[] => {
    const leftMap = new Map(left.map((entry) => [entry.role, entry]));
    const rightMap = new Map(right.map((entry) => [entry.role, entry]));
    const roles = new Set([...leftMap.keys(), ...rightMap.keys()]);
    return [...roles]
        .toSorted((leftRole, rightRole) => leftRole.localeCompare(rightRole))
        .map((role) => ({
            role,
            left: leftMap.get(role),
            right: rightMap.get(role),
        }));
};

export const formatPercentValue = (value: number | undefined): string => {
    if (value === undefined) {
        return "-";
    }
    const pct = value * 100;
    if (Number.isInteger(pct)) {
        return `${pct}%`;
    }
    return `${pct.toFixed(1)}%`;
};

export const formatDeltaPercent = (value: number | undefined): string => {
    if (value === undefined) {
        return "-";
    }
    const pct = value * 100;
    const formatted = Number.isInteger(pct) ? pct.toString() : pct.toFixed(1);
    const sign = pct > 0 ? "+" : "";
    return `${sign}${formatted}%`;
};

export const formatDurationValue = (value: number | undefined): string => {
    if (value === undefined) {
        return "-";
    }
    return `${value.toFixed(2)}s`;
};

export const formatDeltaDuration = (value: number | undefined): string => {
    if (value === undefined) {
        return "-";
    }
    const sign = value > 0 ? "+" : "";
    return `${sign}${value.toFixed(2)}s`;
};

export const getDeltaClassName = (
    delta: number | undefined,
    positiveIsGood: boolean,
): string => {
    if (delta === undefined || delta === 0) {
        return "text-muted-foreground";
    }
    const positiveClass = "text-emerald-600 dark:text-emerald-400";
    if (positiveIsGood) {
        return delta > 0 ? positiveClass : "text-destructive";
    }
    return delta > 0 ? "text-destructive" : positiveClass;
};

export const resolveModelDelta = (
    left: string | undefined,
    right: string | undefined,
): { label: string; className: string } => {
    if (
        left === undefined ||
        left === "" ||
        right === undefined ||
        right === ""
    ) {
        return { label: "-", className: "text-muted-foreground" };
    }
    if (left === right) {
        return { label: "Same", className: "text-muted-foreground" };
    }
    return { label: "Changed", className: "text-foreground" };
};

export const sortReportsByGenerated = (
    left: EvalReportSummary,
    right: EvalReportSummary,
): number =>
    new Date(right.generatedAt).getTime() -
    new Date(left.generatedAt).getTime();
