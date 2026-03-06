import { Terminal } from "@va/shared/components/ai-elements/terminal";
import { Streamdown } from "@va/shared/components/streamdown";
import { Badge } from "@va/shared/components/ui/badge";
import { Button } from "@va/shared/components/ui/button";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@va/shared/components/ui/card";
import {
    Command,
    CommandEmpty,
    CommandGroup,
    CommandInput,
    CommandItem,
    CommandList,
} from "@va/shared/components/ui/command";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@va/shared/components/ui/dialog";
import { Label } from "@va/shared/components/ui/label";
import {
    Popover,
    PopoverContent,
    PopoverTrigger,
} from "@va/shared/components/ui/popover";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@va/shared/components/ui/select";
import { Spinner } from "@va/shared/components/ui/spinner";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@va/shared/components/ui/table";
import {
    ToggleGroup,
    ToggleGroupItem,
} from "@va/shared/components/ui/toggle-group";
import {
    Tooltip,
    TooltipContent,
    TooltipTrigger,
} from "@va/shared/components/ui/tooltip";
import {
    ArrowLeftRight,
    Check,
    ChevronsUpDown,
    FileText,
    RefreshCw,
    X,
} from "lucide-react";
import { type JSX, useCallback, useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";

import {
    type ChartConfig,
    ChartContainer,
    ChartTooltip,
} from "@/components/ui/chart";

import { useAuthenticatedApi } from "../../auth/hooks/use-authenticated-api";
import { PageHeader } from "../../components/page-header";
import { PageSection, PageShell } from "../../components/page-shell";
import {
    InlineError,
    PageError,
    PageLoading,
} from "../../components/page-state";
import {
    fetchEvalReport,
    fetchEvalReportLog,
    fetchEvalReports,
} from "../lib/api";
import {
    buildCompareRows,
    buildModelCompareRows,
    buildModelRoleMap,
    buildReportSummaryMetrics,
    formatBytes,
    formatDeltaDuration,
    formatDeltaPercent,
    formatDurationValue,
    formatModelValue,
    formatOptionalNumber,
    formatPercentValue,
    formatReportMeta,
    formatTimestamp,
    getDeltaClassName,
    parseModelConfigurations,
    parseSummaryTable,
    resolveModelDelta,
    sortReportsByGenerated,
} from "../lib/report-utils";
import type {
    EvalReportDetail,
    EvalReportSummary,
    EvalRunLogFile,
} from "../types";
import { EvalsReportsList } from "./evals-reports-list";
import { EvalsRunCard } from "./evals-run-card";

type ViewMode = "report" | "compare" | "trends" | "models";

interface CompareChartDatum {
    id: string;
    label: string;
    passRate: number | undefined;
    duration: number | undefined;
    chatbotModel?: string;
    guardrailsModel?: string;
    searchModel?: string;
}

interface ModelGroupReportMetrics {
    reportId: string;
    passRate: number | undefined;
    duration: number | undefined;
}

interface ModelGroupEntry {
    key: string;
    label: string;
    reports: EvalReportSummary[];
    metrics: ModelGroupReportMetrics[];
    passRateMedian: number | undefined;
    durationMedian: number | undefined;
    latestAt: number | undefined;
}

const passRateChartConfig = {
    passRate: {
        label: "Pass rate",
        color: "var(--chart-2)",
    },
} satisfies ChartConfig;

const durationChartConfig = {
    duration: {
        label: "Median duration",
        color: "var(--chart-4)",
    },
} satisfies ChartConfig;

const CompareChartTooltip = ({
    active,
    payload,
    metric,
}: {
    active?: boolean;
    payload?: { value?: number; payload?: CompareChartDatum }[];
    metric: "passRate" | "duration";
}): JSX.Element | undefined => {
    if (active !== true || !payload || payload.length === 0) {
        return undefined;
    }
    const entry = payload[0]?.payload;
    if (entry === undefined) {
        return undefined;
    }
    const metricLabel = metric === "passRate" ? "Pass rate" : "Median duration";
    const rawValue = payload[0]?.value;
    const metricValue =
        metric === "passRate"
            ? rawValue === undefined
                ? "-"
                : formatPercentValue(rawValue)
            : rawValue === undefined
              ? "-"
              : formatDurationValue(rawValue);
    return (
        <div className="border-border/50 bg-background grid min-w-[12rem] gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs shadow-xl">
            <div className="font-medium">{entry.label}</div>
            <div className="grid gap-1">
                <div className="flex items-center justify-between gap-3">
                    <span className="text-muted-foreground">{metricLabel}</span>
                    <span className="font-medium tabular-nums">
                        {metricValue}
                    </span>
                </div>
                <div className="text-muted-foreground flex flex-col gap-1">
                    <div className="flex items-center justify-between gap-3">
                        <span>Chatbot</span>
                        <span className="text-foreground">
                            {formatModelValue(entry.chatbotModel)}
                        </span>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                        <span>Guardrails</span>
                        <span className="text-foreground">
                            {formatModelValue(entry.guardrailsModel)}
                        </span>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                        <span>Search</span>
                        <span className="text-foreground">
                            {formatModelValue(entry.searchModel)}
                        </span>
                    </div>
                </div>
            </div>
        </div>
    );
};

type ModelRole = "chatbot" | "guardrails" | "search";

type ModelRoleSet = readonly ModelRole[];

const buildModelComboKey = (
    roleMap: Partial<Record<ModelRole, string>>,
    roles: ModelRoleSet,
): string =>
    roles.map((role) => `${role}:${roleMap[role] ?? "unknown"}`).join("||");

const buildModelComboLabel = (
    roleMap: Partial<Record<ModelRole, string>>,
    roles: ModelRoleSet,
): string => {
    const labelMap: Record<ModelRole, string> = {
        chatbot: "Chatbot",
        guardrails: "Guardrails",
        search: "Search",
    };
    return roles
        .map((role) => `${labelMap[role]}: ${formatModelValue(roleMap[role])}`)
        .join(" | ");
};

const resolveModelRolesForType = (
    reportType: string | undefined,
): ModelRoleSet => {
    if (reportType === undefined) {
        return ["search", "guardrails", "chatbot"];
    }
    const normalized = reportType.toLowerCase();
    if (normalized.includes("search")) {
        return ["search"];
    }
    if (normalized.includes("guardrail")) {
        return ["guardrails"];
    }
    if (normalized.includes("chatbot")) {
        return ["search", "guardrails", "chatbot"];
    }
    return ["search", "guardrails", "chatbot"];
};

const median = (values: number[]): number | undefined => {
    if (values.length === 0) {
        return undefined;
    }
    const sorted = [...values].toSorted((left, right) => left - right);
    const midpoint = Math.floor(sorted.length / 2);
    if (sorted.length % 2 === 1) {
        return sorted[midpoint];
    }
    const lower = sorted[midpoint - 1];
    const upper = sorted[midpoint];
    if (lower === undefined || upper === undefined) {
        return undefined;
    }
    return (lower + upper) / 2;
};

export const EvalsPage = (): JSX.Element => {
    const api = useAuthenticatedApi();
    const [reports, setReports] = useState<EvalReportSummary[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | undefined>();
    const [selectedReportId, setSelectedReportId] = useState<
        string | undefined
    >();
    const [reportDetails, setReportDetails] = useState<
        Record<string, EvalReportDetail | undefined>
    >({});
    const [detailLoadingId, setDetailLoadingId] = useState<
        string | undefined
    >();
    const [detailError, setDetailError] = useState<string | undefined>();
    const [searchValue, setSearchValue] = useState("");
    const [viewMode, setViewMode] = useState<ViewMode>("report");
    const [compareType, setCompareType] = useState<string | undefined>();
    const [compareLeftId, setCompareLeftId] = useState<string | undefined>();
    const [compareRightId, setCompareRightId] = useState<string | undefined>();
    const [compareSelectedIds, setCompareSelectedIds] = useState<string[]>([]);
    const [compareReportsOpen, setCompareReportsOpen] = useState(false);
    const [compareReportsSearch, setCompareReportsSearch] = useState("");
    const [modelGroupKey, setModelGroupKey] = useState<string | undefined>();
    const [reportLogDialogOpen, setReportLogDialogOpen] = useState(false);
    const [reportLogFile, setReportLogFile] = useState<
        EvalRunLogFile | undefined
    >();
    const [reportLogReportId, setReportLogReportId] = useState<
        string | undefined
    >();
    const [reportLogLoading, setReportLogLoading] = useState(false);
    const [reportLogError, setReportLogError] = useState<string | undefined>();

    const loadReports = useCallback(async () => {
        setLoading(true);
        setError(undefined);
        try {
            const response = await fetchEvalReports(api);
            setReports(response);
        } catch (error_) {
            setError(
                error_ instanceof Error
                    ? error_.message
                    : "Failed to load eval reports",
            );
        } finally {
            setLoading(false);
        }
    }, [api]);

    const loadReportDetail = useCallback(
        async (reportId: string) => {
            setDetailLoadingId(reportId);
            setDetailError(undefined);
            try {
                const response = await fetchEvalReport(api, reportId);
                setReportDetails((prev) => ({
                    ...prev,
                    [reportId]: response,
                }));
            } catch (error_) {
                setDetailError(
                    error_ instanceof Error
                        ? error_.message
                        : "Failed to load report",
                );
            } finally {
                setDetailLoadingId((current) =>
                    current === reportId ? undefined : current,
                );
            }
        },
        [api],
    );

    const loadReportLog = useCallback(
        async (reportId: string) => {
            setReportLogLoading(true);
            setReportLogError(undefined);
            try {
                const response = await fetchEvalReportLog(api, reportId);
                setReportLogFile(response);
                setReportLogReportId(reportId);
            } catch (error_) {
                setReportLogError(
                    error_ instanceof Error
                        ? error_.message
                        : "Failed to load report log",
                );
            } finally {
                setReportLogLoading(false);
            }
        },
        [api],
    );

    const handleReportCreated = useCallback(
        (reportId: string) => {
            setSelectedReportId(reportId);
            setViewMode("report");
            void loadReports();
        },
        [loadReports],
    );

    useEffect(() => {
        void loadReports();
    }, [loadReports]);

    useEffect(() => {
        if (reports.length === 0) {
            setSelectedReportId(undefined);
            return;
        }
        setSelectedReportId((current) => {
            if (
                current !== undefined &&
                current !== "" &&
                reports.some((report) => report.id === current)
            ) {
                return current;
            }
            return reports[0]?.id;
        });
    }, [reports]);

    const filteredReports = useMemo(() => {
        const query = searchValue.trim().toLowerCase();
        if (query === "") {
            return reports;
        }
        return reports.filter(
            (report) =>
                report.name.toLowerCase().includes(query) ||
                report.filename.toLowerCase().includes(query),
        );
    }, [reports, searchValue]);

    useEffect(() => {
        if (filteredReports.length === 0) {
            return;
        }
        if (
            selectedReportId === undefined ||
            !filteredReports.some((report) => report.id === selectedReportId)
        ) {
            setSelectedReportId(filteredReports[0]?.id);
        }
    }, [filteredReports, selectedReportId]);

    useEffect(() => {
        setReportLogFile(undefined);
        setReportLogReportId(undefined);
        setReportLogError(undefined);
    }, [selectedReportId]);

    useEffect(() => {
        if (!reportLogDialogOpen || selectedReportId === undefined) {
            return;
        }
        if (reportLogReportId === selectedReportId) {
            return;
        }
        void loadReportLog(selectedReportId);
    }, [
        loadReportLog,
        reportLogDialogOpen,
        reportLogReportId,
        selectedReportId,
    ]);

    const groupedCompareReports = useMemo(() => {
        const groups = new Map<string, EvalReportSummary[]>();
        for (const report of reports) {
            const existing = groups.get(report.name);
            if (existing === undefined) {
                groups.set(report.name, [report]);
            } else {
                existing.push(report);
            }
        }
        for (const group of groups.values()) {
            group.sort(sortReportsByGenerated);
        }
        return groups;
    }, [reports]);

    const compareTypeOptions = useMemo(() => {
        const entries = [...groupedCompareReports.entries()].map(
            ([name, items]) => ({
                name,
                latestAt: new Date(items[0].generatedAt).getTime(),
            }),
        );
        entries.sort((left, right) => right.latestAt - left.latestAt);
        return entries.map((entry) => entry.name);
    }, [groupedCompareReports]);

    const compareGroupReports = useMemo(() => {
        if (compareType === undefined) {
            return [];
        }
        return groupedCompareReports.get(compareType) ?? [];
    }, [compareType, groupedCompareReports]);

    useEffect(() => {
        if (compareTypeOptions.length === 0) {
            setCompareType(undefined);
            return;
        }
        setCompareType((current) =>
            current !== undefined &&
            current !== "" &&
            compareTypeOptions.includes(current)
                ? current
                : compareTypeOptions[0],
        );
    }, [compareTypeOptions]);

    useEffect(() => {
        if (compareGroupReports.length === 0) {
            setCompareLeftId(undefined);
            return;
        }
        setCompareLeftId((current) => {
            if (
                current !== undefined &&
                compareGroupReports.some((report) => report.id === current)
            ) {
                return current;
            }
            return compareGroupReports[0].id;
        });
    }, [compareGroupReports]);

    useEffect(() => {
        if (compareGroupReports.length <= 1) {
            setCompareRightId(undefined);
            return;
        }
        setCompareRightId((current) => {
            if (
                current !== undefined &&
                current !== compareLeftId &&
                compareGroupReports.some((report) => report.id === current)
            ) {
                return current;
            }
            const fallbackReport = compareGroupReports.find(
                (report) => report.id !== compareLeftId,
            );
            return fallbackReport
                ? fallbackReport.id
                : compareGroupReports[0].id;
        });
    }, [compareGroupReports, compareLeftId]);

    useEffect(() => {
        if (compareGroupReports.length === 0) {
            setCompareSelectedIds([]);
            return;
        }
        setCompareSelectedIds((current) => {
            const filtered = current.filter((id) =>
                compareGroupReports.some((report) => report.id === id),
            );
            if (filtered.length > 0) {
                return filtered;
            }
            return compareGroupReports
                .slice(0, Math.min(5, compareGroupReports.length))
                .map((report) => report.id);
        });
    }, [compareGroupReports]);

    useEffect(() => {
        const ids = new Set<string>();
        if (selectedReportId !== undefined) {
            ids.add(selectedReportId);
        }
        if (viewMode === "compare") {
            if (compareLeftId !== undefined) {
                ids.add(compareLeftId);
            }
            if (compareRightId !== undefined) {
                ids.add(compareRightId);
            }
        }
        if (viewMode === "trends") {
            for (const reportId of compareSelectedIds) {
                ids.add(reportId);
            }
        }
        if (viewMode === "models") {
            for (const report of compareGroupReports) {
                ids.add(report.id);
            }
        }
        for (const reportId of ids) {
            if (reportDetails[reportId] === undefined) {
                void loadReportDetail(reportId);
            }
        }
    }, [
        compareGroupReports,
        compareLeftId,
        compareRightId,
        compareSelectedIds,
        loadReportDetail,
        reportDetails,
        selectedReportId,
        viewMode,
    ]);

    useEffect(() => {
        setDetailError(undefined);
    }, [
        compareLeftId,
        compareRightId,
        compareSelectedIds,
        selectedReportId,
        viewMode,
    ]);

    const selectedReportSummary = useMemo(
        () => reports.find((report) => report.id === selectedReportId),
        [reports, selectedReportId],
    );
    const selectedReportDetail =
        selectedReportId === undefined
            ? undefined
            : reportDetails[selectedReportId];
    const detailLoading =
        selectedReportId !== undefined &&
        detailLoadingId === selectedReportId &&
        selectedReportDetail === undefined;
    const reportMeta = selectedReportDetail ?? selectedReportSummary;
    const reportLogOutput =
        reportLogFile?.content ??
        (reportLogLoading ? "Loading log file..." : "Log file not loaded.");
    const reportLogDescription = reportLogFile
        ? `${reportLogFile.filename} · ${formatBytes(reportLogFile.sizeBytes)}`
        : (selectedReportId ?? "Select a report to view the log.");

    const compareLeftSummary = useMemo(
        () =>
            compareLeftId === undefined
                ? undefined
                : reports.find((report) => report.id === compareLeftId),
        [compareLeftId, reports],
    );
    const compareRightSummary = useMemo(
        () =>
            compareRightId === undefined
                ? undefined
                : reports.find((report) => report.id === compareRightId),
        [compareRightId, reports],
    );
    const compareLeftDetail =
        compareLeftId === undefined ? undefined : reportDetails[compareLeftId];
    const compareRightDetail =
        compareRightId === undefined
            ? undefined
            : reportDetails[compareRightId];
    const compareLeftMeta = compareLeftDetail ?? compareLeftSummary;
    const compareRightMeta = compareRightDetail ?? compareRightSummary;

    const compareLoading =
        viewMode === "compare" &&
        ((compareLeftId !== undefined &&
            reportDetails[compareLeftId] === undefined) ||
            (compareRightId !== undefined &&
                reportDetails[compareRightId] === undefined));

    const compareRows = useMemo(() => {
        if (!compareLeftDetail || !compareRightDetail) {
            return [];
        }
        return buildCompareRows(
            parseSummaryTable(compareLeftDetail.content),
            parseSummaryTable(compareRightDetail.content),
        );
    }, [compareLeftDetail, compareRightDetail]);

    const compareModelRows = useMemo(() => {
        if (!compareLeftDetail || !compareRightDetail) {
            return [];
        }
        return buildModelCompareRows(
            parseModelConfigurations(compareLeftDetail.content),
            parseModelConfigurations(compareRightDetail.content),
        );
    }, [compareLeftDetail, compareRightDetail]);

    const compareSelectedSet = useMemo(
        () => new Set(compareSelectedIds),
        [compareSelectedIds],
    );

    const compareReportsLabel =
        compareSelectedIds.length === 0
            ? "Select reports"
            : `${compareSelectedIds.length} report${
                  compareSelectedIds.length === 1 ? "" : "s"
              } selected`;

    const compareReportsEmptyLabel =
        compareGroupReports.length === 0
            ? "No reports available."
            : "No reports match your search.";

    const filteredCompareReports = useMemo(() => {
        const query = compareReportsSearch.trim().toLowerCase();
        if (query === "") {
            return compareGroupReports;
        }
        return compareGroupReports.filter((report) => {
            const label = `${formatTimestamp(report.generatedAt)} ${report.filename}`;
            return label.toLowerCase().includes(query);
        });
    }, [compareGroupReports, compareReportsSearch]);

    const compareSelectedReports = useMemo(
        () =>
            compareGroupReports.filter((report) =>
                compareSelectedSet.has(report.id),
            ),
        [compareGroupReports, compareSelectedSet],
    );

    const compareSelectedReportsSorted = useMemo(() => {
        const reportsSorted = [...compareSelectedReports];
        reportsSorted.sort(
            (left, right) =>
                new Date(left.generatedAt).getTime() -
                new Date(right.generatedAt).getTime(),
        );
        return reportsSorted;
    }, [compareSelectedReports]);

    const compareChartsLoading =
        viewMode === "trends" &&
        compareSelectedReports.some(
            (report) => reportDetails[report.id] === undefined,
        );

    const compareChartData = useMemo(
        () =>
            compareSelectedReportsSorted.map((report) => {
                const detail = reportDetails[report.id];
                const metrics =
                    detail === undefined
                        ? undefined
                        : buildReportSummaryMetrics(detail.content);
                const roleMap =
                    detail === undefined
                        ? {}
                        : buildModelRoleMap(detail.content);
                return {
                    id: report.id,
                    label: formatTimestamp(report.generatedAt),
                    passRate: metrics?.passRateAverage,
                    duration: metrics?.durationMedianAverage,
                    chatbotModel: roleMap.chatbot,
                    guardrailsModel: roleMap.guardrails,
                    searchModel: roleMap.search,
                } satisfies CompareChartDatum;
            }),
        [compareSelectedReportsSorted, reportDetails],
    );

    const compareChartsHaveData = compareChartData.some(
        (entry) => entry.passRate !== undefined || entry.duration !== undefined,
    );

    const modelGroups = useMemo(() => {
        const groups = new Map<string, ModelGroupEntry>();
        const missingReports: string[] = [];
        const roles = resolveModelRolesForType(compareType);
        for (const report of compareGroupReports) {
            const detail = reportDetails[report.id];
            if (detail === undefined) {
                missingReports.push(report.id);
            } else {
                const roleMap = buildModelRoleMap(detail.content);
                const key = buildModelComboKey(roleMap, roles);
                const label = buildModelComboLabel(roleMap, roles);
                const metrics = buildReportSummaryMetrics(detail.content);
                const entry = groups.get(key) ?? {
                    key,
                    label,
                    reports: [],
                    metrics: [],
                    passRateMedian: undefined,
                    durationMedian: undefined,
                    latestAt: undefined,
                };
                entry.reports.push(report);
                entry.metrics.push({
                    reportId: report.id,
                    passRate: metrics?.passRateAverage,
                    duration: metrics?.durationMedianAverage,
                });
                const reportTime = new Date(report.generatedAt).getTime();
                entry.latestAt =
                    entry.latestAt === undefined
                        ? reportTime
                        : Math.max(entry.latestAt, reportTime);
                groups.set(key, entry);
            }
        }
        const entries = [...groups.values()].map((entry) => {
            const passRates = entry.metrics
                .map((metric) => metric.passRate)
                .filter((value): value is number => value !== undefined);
            const durations = entry.metrics
                .map((metric) => metric.duration)
                .filter((value): value is number => value !== undefined);
            return {
                ...entry,
                passRateMedian: median(passRates),
                durationMedian: median(durations),
            } satisfies ModelGroupEntry;
        });
        entries.sort((left, right) => {
            const leftTime = left.latestAt ?? 0;
            const rightTime = right.latestAt ?? 0;
            return rightTime - leftTime;
        });
        return {
            entries,
            missingReports,
        };
    }, [compareGroupReports, compareType, reportDetails]);

    useEffect(() => {
        if (modelGroups.entries.length === 0) {
            setModelGroupKey(undefined);
            return;
        }
        setModelGroupKey((current) =>
            current !== undefined &&
            modelGroups.entries.some((entry) => entry.key === current)
                ? current
                : modelGroups.entries[0]?.key,
        );
    }, [modelGroups.entries]);

    const selectedModelGroup =
        modelGroupKey === undefined
            ? undefined
            : modelGroups.entries.find((entry) => entry.key === modelGroupKey);

    const modelGroupsLoading =
        viewMode === "models" && modelGroups.missingReports.length > 0;

    const selectedModelGroupMetrics = useMemo(() => {
        const metrics = new Map<string, ModelGroupReportMetrics>();
        if (selectedModelGroup !== undefined) {
            for (const entry of selectedModelGroup.metrics) {
                metrics.set(entry.reportId, entry);
            }
        }
        return metrics;
    }, [selectedModelGroup]);

    const canSwapCompare =
        compareLeftId !== undefined && compareRightId !== undefined;

    const handleSwapCompare = useCallback(() => {
        if (!canSwapCompare) {
            return;
        }
        setCompareLeftId(compareRightId);
        setCompareRightId(compareLeftId);
    }, [canSwapCompare, compareLeftId, compareRightId]);

    const toggleCompareReport = useCallback((reportId: string): void => {
        setCompareSelectedIds((current) =>
            current.includes(reportId)
                ? current.filter((id) => id !== reportId)
                : [...current, reportId],
        );
    }, []);

    const handleSelectAllCompareReports = useCallback(() => {
        setCompareSelectedIds(compareGroupReports.map((report) => report.id));
    }, [compareGroupReports]);

    const handleClearCompareReports = useCallback(() => {
        setCompareSelectedIds([]);
    }, []);

    const listDescription = ((): string => {
        if (reports.length === 0) {
            return "No eval reports have been generated yet.";
        }
        if (searchValue.trim() !== "") {
            return `Showing ${filteredReports.length} of ${reports.length} reports.`;
        }
        return `${reports.length} report${reports.length === 1 ? "" : "s"} available.`;
    })();

    if (loading && reports.length === 0) {
        return <PageLoading />;
    }

    if (error !== undefined && reports.length === 0) {
        return (
            <PageError
                message={error}
                onRetry={() => void loadReports()}
            />
        );
    }

    return (
        <PageShell variant="dashboard">
            <PageHeader title="Evals">
                <Button
                    onClick={() => {
                        setDetailError(undefined);
                        setReportDetails({});
                        void loadReports();
                    }}
                    size="sm"
                    variant="outline"
                >
                    <RefreshCw className="mr-2 size-4" />
                    Refresh
                </Button>
            </PageHeader>

            {error !== undefined && reports.length > 0 && (
                <PageSection>
                    <InlineError
                        message={error}
                        onRetry={() => void loadReports()}
                    />
                </PageSection>
            )}

            <PageSection>
                <EvalsRunCard onReportCreated={handleReportCreated} />
            </PageSection>

            <PageSection className="grid grid-cols-1 gap-4 @3xl/main:grid-cols-[360px_minmax(0,1fr)]">
                <EvalsReportsList
                    filteredReports={filteredReports}
                    listDescription={listDescription}
                    onSearchChange={setSearchValue}
                    onSelectReport={setSelectedReportId}
                    searchValue={searchValue}
                    selectedReportId={selectedReportId}
                />

                <Card className="min-h-0">
                    {viewMode === "report" ? (
                        <>
                            <CardHeader className="gap-3">
                                <div className="flex flex-wrap items-center justify-between gap-2">
                                    <div>
                                        <CardTitle>Report</CardTitle>
                                        <CardDescription>
                                            {selectedReportSummary === undefined
                                                ? "Select a report to view details."
                                                : selectedReportSummary.name}
                                        </CardDescription>
                                    </div>
                                    <div className="flex flex-wrap items-center gap-2">
                                        <Dialog
                                            onOpenChange={
                                                setReportLogDialogOpen
                                            }
                                            open={reportLogDialogOpen}
                                        >
                                            <DialogTrigger asChild>
                                                <Button
                                                    disabled={
                                                        selectedReportId ===
                                                        undefined
                                                    }
                                                    size="sm"
                                                    variant="outline"
                                                >
                                                    <FileText className="mr-2 size-4" />
                                                    View log
                                                </Button>
                                            </DialogTrigger>
                                            <DialogContent className="flex h-[90vh] w-[94vw] max-w-[94vw] flex-col sm:max-w-[94vw]">
                                                <DialogHeader>
                                                    <DialogTitle>
                                                        Report log
                                                    </DialogTitle>
                                                    <DialogDescription>
                                                        {reportLogDescription}
                                                    </DialogDescription>
                                                </DialogHeader>
                                                <div className="flex items-center justify-between">
                                                    <Button
                                                        disabled={
                                                            selectedReportId ===
                                                                undefined ||
                                                            reportLogLoading
                                                        }
                                                        onClick={() => {
                                                            if (
                                                                selectedReportId ===
                                                                undefined
                                                            ) {
                                                                return;
                                                            }
                                                            void loadReportLog(
                                                                selectedReportId,
                                                            );
                                                        }}
                                                        size="sm"
                                                        type="button"
                                                        variant="outline"
                                                    >
                                                        Reload log
                                                    </Button>
                                                </div>
                                                {reportLogError !==
                                                    undefined && (
                                                    <InlineError
                                                        message={reportLogError}
                                                    />
                                                )}
                                                <Terminal
                                                    className="min-h-0 flex-1 [&>div:last-child]:h-full [&>div:last-child]:max-h-none"
                                                    output={reportLogOutput}
                                                />
                                            </DialogContent>
                                        </Dialog>
                                        <ToggleGroup
                                            onValueChange={(value) => {
                                                if (
                                                    value === "report" ||
                                                    value === "compare" ||
                                                    value === "trends" ||
                                                    value === "models"
                                                ) {
                                                    setViewMode(value);
                                                }
                                            }}
                                            size="sm"
                                            type="single"
                                            value={viewMode}
                                            variant="outline"
                                        >
                                            <ToggleGroupItem value="report">
                                                Report
                                            </ToggleGroupItem>
                                            <ToggleGroupItem value="compare">
                                                Compare
                                            </ToggleGroupItem>
                                            <ToggleGroupItem value="trends">
                                                Trends
                                            </ToggleGroupItem>
                                            <ToggleGroupItem value="models">
                                                Models
                                            </ToggleGroupItem>
                                        </ToggleGroup>
                                    </div>
                                </div>
                                {reportMeta !== undefined && (
                                    <div className="text-muted-foreground flex flex-wrap items-center gap-2 text-xs">
                                        <span>
                                            Generated{" "}
                                            {formatTimestamp(
                                                reportMeta.generatedAt,
                                            )}
                                        </span>
                                        <span className="text-muted-foreground">
                                            •
                                        </span>
                                        <span>
                                            Repeats{" "}
                                            {formatOptionalNumber(
                                                reportMeta.repeats,
                                            )}
                                        </span>
                                        <span className="text-muted-foreground">
                                            •
                                        </span>
                                        <span>
                                            Concurrency{" "}
                                            {formatOptionalNumber(
                                                reportMeta.concurrency,
                                            )}
                                        </span>
                                        <span className="text-muted-foreground">
                                            •
                                        </span>
                                        <span>
                                            {formatBytes(reportMeta.sizeBytes)}
                                        </span>
                                    </div>
                                )}
                            </CardHeader>
                            <CardContent className="min-h-[240px]">
                                {detailError !== undefined &&
                                    selectedReportId !== undefined && (
                                        <InlineError
                                            message={detailError}
                                            onRetry={() =>
                                                void loadReportDetail(
                                                    selectedReportId,
                                                )
                                            }
                                        />
                                    )}
                                {selectedReportId === undefined ? (
                                    <div className="text-muted-foreground text-sm">
                                        No eval reports are available yet.
                                    </div>
                                ) : detailLoading ? (
                                    <div className="text-muted-foreground flex items-center gap-2 text-sm">
                                        <Spinner className="size-4" />
                                        Loading report...
                                    </div>
                                ) : selectedReportDetail === undefined ? (
                                    <div className="text-muted-foreground text-sm">
                                        Select a report to view its markdown
                                        output.
                                    </div>
                                ) : (
                                    <Streamdown className="max-w-none break-words">
                                        {selectedReportDetail.content}
                                    </Streamdown>
                                )}
                            </CardContent>
                        </>
                    ) : viewMode === "compare" ? (
                        <>
                            <CardHeader className="gap-3">
                                <div className="flex flex-wrap items-center justify-between gap-2">
                                    <div>
                                        <CardTitle>Compare</CardTitle>
                                        <CardDescription>
                                            {compareType ??
                                                "Select a report type to compare."}
                                        </CardDescription>
                                    </div>
                                    <ToggleGroup
                                        onValueChange={(value) => {
                                            if (
                                                value === "report" ||
                                                value === "compare" ||
                                                value === "trends" ||
                                                value === "models"
                                            ) {
                                                setViewMode(value);
                                            }
                                        }}
                                        size="sm"
                                        type="single"
                                        value={viewMode}
                                        variant="outline"
                                    >
                                        <ToggleGroupItem value="report">
                                            Report
                                        </ToggleGroupItem>
                                        <ToggleGroupItem value="compare">
                                            Compare
                                        </ToggleGroupItem>
                                        <ToggleGroupItem value="trends">
                                            Trends
                                        </ToggleGroupItem>
                                        <ToggleGroupItem value="models">
                                            Models
                                        </ToggleGroupItem>
                                    </ToggleGroup>
                                </div>
                            </CardHeader>
                            <CardContent className="min-h-[240px]">
                                {compareTypeOptions.length === 0 ? (
                                    <div className="text-muted-foreground text-sm">
                                        No eval reports are available to compare
                                        yet.
                                    </div>
                                ) : (
                                    <div className="flex flex-col gap-4">
                                        <div className="grid gap-3 @lg/main:grid-cols-[1fr_1fr_auto_1fr]">
                                            <div className="flex flex-col gap-1">
                                                <Label className="text-muted-foreground text-xs">
                                                    Type
                                                </Label>
                                                <Select
                                                    onValueChange={(value) => {
                                                        setCompareType(value);
                                                    }}
                                                    value={compareType}
                                                >
                                                    <SelectTrigger className="w-full">
                                                        <SelectValue placeholder="Select type" />
                                                    </SelectTrigger>
                                                    <SelectContent>
                                                        {compareTypeOptions.map(
                                                            (type) => (
                                                                <SelectItem
                                                                    key={type}
                                                                    value={type}
                                                                >
                                                                    {type}
                                                                </SelectItem>
                                                            ),
                                                        )}
                                                    </SelectContent>
                                                </Select>
                                            </div>
                                            <div className="flex flex-col gap-1">
                                                <Label className="text-muted-foreground text-xs">
                                                    Baseline
                                                </Label>
                                                <Select
                                                    onValueChange={(value) => {
                                                        setCompareLeftId(value);
                                                    }}
                                                    value={compareLeftId}
                                                >
                                                    <SelectTrigger className="w-full">
                                                        <SelectValue placeholder="Select report" />
                                                    </SelectTrigger>
                                                    <SelectContent>
                                                        {compareGroupReports.map(
                                                            (report) => (
                                                                <SelectItem
                                                                    key={
                                                                        report.id
                                                                    }
                                                                    value={
                                                                        report.id
                                                                    }
                                                                >
                                                                    <span className="flex flex-col text-left">
                                                                        <span>
                                                                            {formatTimestamp(
                                                                                report.generatedAt,
                                                                            )}
                                                                        </span>
                                                                        <span className="text-muted-foreground text-xs">
                                                                            {
                                                                                report.filename
                                                                            }
                                                                        </span>
                                                                    </span>
                                                                </SelectItem>
                                                            ),
                                                        )}
                                                    </SelectContent>
                                                </Select>
                                            </div>
                                            <div className="flex flex-col gap-1">
                                                <Label className="text-muted-foreground text-xs">
                                                    Swap
                                                </Label>
                                                <Tooltip>
                                                    <TooltipTrigger asChild>
                                                        <Button
                                                            aria-label="Swap baseline and compare reports"
                                                            disabled={
                                                                !canSwapCompare
                                                            }
                                                            onClick={
                                                                handleSwapCompare
                                                            }
                                                            size="icon-sm"
                                                            type="button"
                                                            variant="outline"
                                                        >
                                                            <ArrowLeftRight className="size-3" />
                                                        </Button>
                                                    </TooltipTrigger>
                                                    <TooltipContent side="top">
                                                        Swap baseline and
                                                        compare
                                                    </TooltipContent>
                                                </Tooltip>
                                            </div>
                                            <div className="flex flex-col gap-1">
                                                <Label className="text-muted-foreground text-xs">
                                                    Compare
                                                </Label>
                                                <Select
                                                    disabled={
                                                        compareGroupReports.length <=
                                                        1
                                                    }
                                                    onValueChange={(value) => {
                                                        if (
                                                            value ===
                                                            compareLeftId
                                                        ) {
                                                            return;
                                                        }
                                                        setCompareRightId(
                                                            value,
                                                        );
                                                    }}
                                                    value={compareRightId}
                                                >
                                                    <SelectTrigger className="w-full">
                                                        <SelectValue placeholder="Select report" />
                                                    </SelectTrigger>
                                                    <SelectContent>
                                                        {compareGroupReports
                                                            .filter(
                                                                (report) =>
                                                                    report.id !==
                                                                    compareLeftId,
                                                            )
                                                            .map((report) => (
                                                                <SelectItem
                                                                    key={
                                                                        report.id
                                                                    }
                                                                    value={
                                                                        report.id
                                                                    }
                                                                >
                                                                    <span className="flex flex-col text-left">
                                                                        <span>
                                                                            {formatTimestamp(
                                                                                report.generatedAt,
                                                                            )}
                                                                        </span>
                                                                        <span className="text-muted-foreground text-xs">
                                                                            {
                                                                                report.filename
                                                                            }
                                                                        </span>
                                                                    </span>
                                                                </SelectItem>
                                                            ))}
                                                    </SelectContent>
                                                </Select>
                                            </div>
                                        </div>
                                        <div className="text-muted-foreground grid gap-3 text-xs @lg/main:grid-cols-2">
                                            <div>
                                                <div className="text-foreground text-xs font-semibold">
                                                    Baseline
                                                </div>
                                                <div>
                                                    {compareLeftMeta ===
                                                    undefined
                                                        ? "Select a baseline report to compare."
                                                        : formatReportMeta(
                                                              compareLeftMeta,
                                                          )}
                                                </div>
                                            </div>
                                            <div>
                                                <div className="text-foreground text-xs font-semibold">
                                                    Compare
                                                </div>
                                                <div>
                                                    {compareRightMeta ===
                                                    undefined
                                                        ? "Select a report to compare against the baseline."
                                                        : formatReportMeta(
                                                              compareRightMeta,
                                                          )}
                                                </div>
                                            </div>
                                        </div>
                                        {detailError !== undefined && (
                                            <InlineError
                                                message={detailError}
                                                onRetry={() => {
                                                    if (
                                                        compareLeftId !==
                                                        undefined
                                                    ) {
                                                        void loadReportDetail(
                                                            compareLeftId,
                                                        );
                                                    }
                                                    if (
                                                        compareRightId !==
                                                            undefined &&
                                                        compareRightId !==
                                                            compareLeftId
                                                    ) {
                                                        void loadReportDetail(
                                                            compareRightId,
                                                        );
                                                    }
                                                }}
                                            />
                                        )}
                                        {compareGroupReports.length < 2 ? (
                                            <div className="text-muted-foreground text-sm">
                                                Select a report type with at
                                                least two runs to compare.
                                            </div>
                                        ) : compareLeftId === undefined ||
                                          compareRightId === undefined ? (
                                            <div className="text-muted-foreground text-sm">
                                                Select two reports to compare.
                                            </div>
                                        ) : compareLoading ? (
                                            <div className="text-muted-foreground flex items-center gap-2 text-sm">
                                                <Spinner className="size-4" />
                                                Loading comparison...
                                            </div>
                                        ) : (
                                            <div className="flex flex-col gap-6">
                                                <div className="flex flex-col gap-2">
                                                    <div className="text-foreground text-xs font-semibold">
                                                        Models
                                                    </div>
                                                    {compareModelRows.length ===
                                                    0 ? (
                                                        <div className="text-muted-foreground text-sm">
                                                            No model
                                                            configuration data
                                                            available.
                                                        </div>
                                                    ) : (
                                                        <div className="overflow-x-auto">
                                                            <Table>
                                                                <TableHeader>
                                                                    <TableRow>
                                                                        <TableHead>
                                                                            Role
                                                                        </TableHead>
                                                                        <TableHead>
                                                                            Baseline
                                                                        </TableHead>
                                                                        <TableHead>
                                                                            Compare
                                                                        </TableHead>
                                                                        <TableHead>
                                                                            Δ
                                                                        </TableHead>
                                                                    </TableRow>
                                                                </TableHeader>
                                                                <TableBody>
                                                                    {compareModelRows.map(
                                                                        (
                                                                            row,
                                                                        ) => {
                                                                            const leftModel =
                                                                                row
                                                                                    .left
                                                                                    ?.model;
                                                                            const rightModel =
                                                                                row
                                                                                    .right
                                                                                    ?.model;
                                                                            const delta =
                                                                                resolveModelDelta(
                                                                                    leftModel,
                                                                                    rightModel,
                                                                                );
                                                                            return (
                                                                                <TableRow
                                                                                    key={
                                                                                        row.role
                                                                                    }
                                                                                >
                                                                                    <TableCell className="font-medium">
                                                                                        {
                                                                                            row.role
                                                                                        }
                                                                                    </TableCell>
                                                                                    <TableCell className="text-xs break-words">
                                                                                        {formatModelValue(
                                                                                            leftModel,
                                                                                        )}
                                                                                    </TableCell>
                                                                                    <TableCell className="text-xs break-words">
                                                                                        {formatModelValue(
                                                                                            rightModel,
                                                                                        )}
                                                                                    </TableCell>
                                                                                    <TableCell
                                                                                        className={`text-xs ${delta.className}`}
                                                                                    >
                                                                                        {
                                                                                            delta.label
                                                                                        }
                                                                                    </TableCell>
                                                                                </TableRow>
                                                                            );
                                                                        },
                                                                    )}
                                                                </TableBody>
                                                            </Table>
                                                        </div>
                                                    )}
                                                </div>
                                                <div className="flex flex-col gap-2">
                                                    <div className="text-foreground text-xs font-semibold">
                                                        Summary
                                                    </div>
                                                    {compareRows.length ===
                                                    0 ? (
                                                        <div className="text-muted-foreground text-sm">
                                                            No summary data
                                                            available for
                                                            comparison.
                                                        </div>
                                                    ) : (
                                                        <div className="overflow-x-auto">
                                                            <Table>
                                                                <TableHeader>
                                                                    <TableRow>
                                                                        <TableHead>
                                                                            Case
                                                                        </TableHead>
                                                                        <TableHead className="text-right">
                                                                            Pass
                                                                            (Baseline)
                                                                        </TableHead>
                                                                        <TableHead className="text-right">
                                                                            Pass
                                                                            (Compare)
                                                                        </TableHead>
                                                                        <TableHead className="text-right">
                                                                            Δ
                                                                        </TableHead>
                                                                        <TableHead className="text-right">
                                                                            Errors
                                                                            (Baseline)
                                                                        </TableHead>
                                                                        <TableHead className="text-right">
                                                                            Errors
                                                                            (Compare)
                                                                        </TableHead>
                                                                        <TableHead className="text-right">
                                                                            Δ
                                                                        </TableHead>
                                                                        <TableHead className="text-right">
                                                                            Median
                                                                            (Baseline)
                                                                        </TableHead>
                                                                        <TableHead className="text-right">
                                                                            Median
                                                                            (Compare)
                                                                        </TableHead>
                                                                        <TableHead className="text-right">
                                                                            Δ
                                                                        </TableHead>
                                                                    </TableRow>
                                                                </TableHeader>
                                                                <TableBody>
                                                                    {compareRows.map(
                                                                        (
                                                                            row,
                                                                        ) => {
                                                                            const {
                                                                                caseName,
                                                                                left,
                                                                                right,
                                                                            } =
                                                                                row;
                                                                            const leftPassRate =
                                                                                left?.passRate;
                                                                            const rightPassRate =
                                                                                right?.passRate;
                                                                            const passDelta =
                                                                                leftPassRate !==
                                                                                    undefined &&
                                                                                rightPassRate !==
                                                                                    undefined
                                                                                    ? rightPassRate -
                                                                                      leftPassRate
                                                                                    : undefined;
                                                                            const leftErrorRate =
                                                                                left?.runtimeErrorRate;
                                                                            const rightErrorRate =
                                                                                right?.runtimeErrorRate;
                                                                            const errorDelta =
                                                                                leftErrorRate !==
                                                                                    undefined &&
                                                                                rightErrorRate !==
                                                                                    undefined
                                                                                    ? rightErrorRate -
                                                                                      leftErrorRate
                                                                                    : undefined;
                                                                            const leftDuration =
                                                                                left?.durationMedian;
                                                                            const rightDuration =
                                                                                right?.durationMedian;
                                                                            const durationDelta =
                                                                                leftDuration !==
                                                                                    undefined &&
                                                                                rightDuration !==
                                                                                    undefined
                                                                                    ? rightDuration -
                                                                                      leftDuration
                                                                                    : undefined;
                                                                            return (
                                                                                <TableRow
                                                                                    key={
                                                                                        caseName
                                                                                    }
                                                                                >
                                                                                    <TableCell className="font-medium">
                                                                                        {
                                                                                            caseName
                                                                                        }
                                                                                    </TableCell>
                                                                                    <TableCell className="text-right tabular-nums">
                                                                                        {formatPercentValue(
                                                                                            leftPassRate,
                                                                                        )}
                                                                                    </TableCell>
                                                                                    <TableCell className="text-right tabular-nums">
                                                                                        {formatPercentValue(
                                                                                            rightPassRate,
                                                                                        )}
                                                                                    </TableCell>
                                                                                    <TableCell
                                                                                        className={`text-right tabular-nums ${getDeltaClassName(
                                                                                            passDelta,
                                                                                            true,
                                                                                        )}`}
                                                                                    >
                                                                                        {formatDeltaPercent(
                                                                                            passDelta,
                                                                                        )}
                                                                                    </TableCell>
                                                                                    <TableCell className="text-right tabular-nums">
                                                                                        {formatPercentValue(
                                                                                            leftErrorRate,
                                                                                        )}
                                                                                    </TableCell>
                                                                                    <TableCell className="text-right tabular-nums">
                                                                                        {formatPercentValue(
                                                                                            rightErrorRate,
                                                                                        )}
                                                                                    </TableCell>
                                                                                    <TableCell
                                                                                        className={`text-right tabular-nums ${getDeltaClassName(
                                                                                            errorDelta,
                                                                                            false,
                                                                                        )}`}
                                                                                    >
                                                                                        {formatDeltaPercent(
                                                                                            errorDelta,
                                                                                        )}
                                                                                    </TableCell>
                                                                                    <TableCell className="text-right tabular-nums">
                                                                                        {formatDurationValue(
                                                                                            leftDuration,
                                                                                        )}
                                                                                    </TableCell>
                                                                                    <TableCell className="text-right tabular-nums">
                                                                                        {formatDurationValue(
                                                                                            rightDuration,
                                                                                        )}
                                                                                    </TableCell>
                                                                                    <TableCell
                                                                                        className={`text-right tabular-nums ${getDeltaClassName(
                                                                                            durationDelta,
                                                                                            false,
                                                                                        )}`}
                                                                                    >
                                                                                        {formatDeltaDuration(
                                                                                            durationDelta,
                                                                                        )}
                                                                                    </TableCell>
                                                                                </TableRow>
                                                                            );
                                                                        },
                                                                    )}
                                                                </TableBody>
                                                            </Table>
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                )}
                            </CardContent>
                        </>
                    ) : viewMode === "trends" ? (
                        <>
                            <CardHeader className="gap-3">
                                <div className="flex flex-wrap items-center justify-between gap-2">
                                    <div>
                                        <CardTitle>Trends</CardTitle>
                                        <CardDescription>
                                            {compareType ??
                                                "Select a report type to view trends."}
                                        </CardDescription>
                                    </div>
                                    <ToggleGroup
                                        onValueChange={(value) => {
                                            if (
                                                value === "report" ||
                                                value === "compare" ||
                                                value === "trends" ||
                                                value === "models"
                                            ) {
                                                setViewMode(value);
                                            }
                                        }}
                                        size="sm"
                                        type="single"
                                        value={viewMode}
                                        variant="outline"
                                    >
                                        <ToggleGroupItem value="report">
                                            Report
                                        </ToggleGroupItem>
                                        <ToggleGroupItem value="compare">
                                            Compare
                                        </ToggleGroupItem>
                                        <ToggleGroupItem value="trends">
                                            Trends
                                        </ToggleGroupItem>
                                        <ToggleGroupItem value="models">
                                            Models
                                        </ToggleGroupItem>
                                    </ToggleGroup>
                                </div>
                            </CardHeader>
                            <CardContent className="min-h-[240px]">
                                {compareTypeOptions.length === 0 ? (
                                    <div className="text-muted-foreground text-sm">
                                        No eval reports are available to trend
                                        yet.
                                    </div>
                                ) : (
                                    <div className="flex flex-col gap-4">
                                        <div className="grid gap-3 @lg/main:grid-cols-[1fr_1fr]">
                                            <div className="flex flex-col gap-1">
                                                <Label className="text-muted-foreground text-xs">
                                                    Type
                                                </Label>
                                                <Select
                                                    onValueChange={(value) => {
                                                        setCompareType(value);
                                                    }}
                                                    value={compareType}
                                                >
                                                    <SelectTrigger className="w-full">
                                                        <SelectValue placeholder="Select type" />
                                                    </SelectTrigger>
                                                    <SelectContent>
                                                        {compareTypeOptions.map(
                                                            (type) => (
                                                                <SelectItem
                                                                    key={type}
                                                                    value={type}
                                                                >
                                                                    {type}
                                                                </SelectItem>
                                                            ),
                                                        )}
                                                    </SelectContent>
                                                </Select>
                                            </div>
                                            <div className="flex flex-col gap-1">
                                                <Label className="text-muted-foreground text-xs">
                                                    Reports
                                                </Label>
                                                <Popover
                                                    onOpenChange={(
                                                        nextOpen,
                                                    ) => {
                                                        setCompareReportsOpen(
                                                            nextOpen,
                                                        );
                                                        if (!nextOpen) {
                                                            setCompareReportsSearch(
                                                                "",
                                                            );
                                                        }
                                                    }}
                                                    open={compareReportsOpen}
                                                >
                                                    <PopoverTrigger asChild>
                                                        <Button
                                                            aria-expanded={
                                                                compareReportsOpen
                                                            }
                                                            className="h-9 justify-between"
                                                            role="combobox"
                                                            type="button"
                                                            variant="outline"
                                                        >
                                                            <span className="truncate">
                                                                {
                                                                    compareReportsLabel
                                                                }
                                                            </span>
                                                            <ChevronsUpDown className="text-muted-foreground size-4" />
                                                        </Button>
                                                    </PopoverTrigger>
                                                    <PopoverContent
                                                        align="start"
                                                        className="w-[340px] p-0"
                                                    >
                                                        <Command
                                                            shouldFilter={false}
                                                        >
                                                            <CommandInput
                                                                onValueChange={
                                                                    setCompareReportsSearch
                                                                }
                                                                placeholder="Search reports..."
                                                                value={
                                                                    compareReportsSearch
                                                                }
                                                            />
                                                            <div className="text-muted-foreground flex items-center justify-between gap-2 border-b px-3 py-2 text-xs">
                                                                <span>
                                                                    {
                                                                        compareGroupReports.length
                                                                    }{" "}
                                                                    available
                                                                </span>
                                                                <div className="flex items-center gap-2">
                                                                    <Button
                                                                        disabled={
                                                                            compareGroupReports.length ===
                                                                            0
                                                                        }
                                                                        onClick={
                                                                            handleSelectAllCompareReports
                                                                        }
                                                                        size="sm"
                                                                        type="button"
                                                                        variant="ghost"
                                                                    >
                                                                        Select
                                                                        all
                                                                    </Button>
                                                                    <Button
                                                                        disabled={
                                                                            compareSelectedIds.length ===
                                                                            0
                                                                        }
                                                                        onClick={
                                                                            handleClearCompareReports
                                                                        }
                                                                        size="sm"
                                                                        type="button"
                                                                        variant="ghost"
                                                                    >
                                                                        Clear
                                                                    </Button>
                                                                </div>
                                                            </div>
                                                            <CommandList>
                                                                <CommandEmpty>
                                                                    {
                                                                        compareReportsEmptyLabel
                                                                    }
                                                                </CommandEmpty>
                                                                <CommandGroup>
                                                                    {filteredCompareReports.map(
                                                                        (
                                                                            report,
                                                                        ) => {
                                                                            const isSelected =
                                                                                compareSelectedSet.has(
                                                                                    report.id,
                                                                                );
                                                                            return (
                                                                                <CommandItem
                                                                                    key={
                                                                                        report.id
                                                                                    }
                                                                                    onSelect={() => {
                                                                                        toggleCompareReport(
                                                                                            report.id,
                                                                                        );
                                                                                    }}
                                                                                    value={
                                                                                        report.id
                                                                                    }
                                                                                >
                                                                                    <Check
                                                                                        className={`size-4 ${isSelected ? "opacity-100" : "opacity-0"}`}
                                                                                    />
                                                                                    <span className="flex flex-col text-left">
                                                                                        <span>
                                                                                            {formatTimestamp(
                                                                                                report.generatedAt,
                                                                                            )}
                                                                                        </span>
                                                                                        <span className="text-muted-foreground text-xs">
                                                                                            {
                                                                                                report.filename
                                                                                            }
                                                                                        </span>
                                                                                    </span>
                                                                                </CommandItem>
                                                                            );
                                                                        },
                                                                    )}
                                                                </CommandGroup>
                                                            </CommandList>
                                                        </Command>
                                                    </PopoverContent>
                                                </Popover>
                                                {compareSelectedReports.length >
                                                    0 && (
                                                    <div className="flex flex-wrap gap-2 pt-2">
                                                        {compareSelectedReportsSorted.map(
                                                            (report) => (
                                                                <Badge
                                                                    className="gap-1"
                                                                    key={
                                                                        report.id
                                                                    }
                                                                    variant="secondary"
                                                                >
                                                                    <span>
                                                                        {formatTimestamp(
                                                                            report.generatedAt,
                                                                        )}
                                                                    </span>
                                                                    <button
                                                                        aria-label={`Remove ${report.filename}`}
                                                                        className="text-muted-foreground hover:text-foreground"
                                                                        onClick={(
                                                                            event,
                                                                        ) => {
                                                                            event.stopPropagation();
                                                                            toggleCompareReport(
                                                                                report.id,
                                                                            );
                                                                        }}
                                                                        type="button"
                                                                    >
                                                                        <X className="size-3" />
                                                                    </button>
                                                                </Badge>
                                                            ),
                                                        )}
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                        {detailError !== undefined && (
                                            <InlineError
                                                message={detailError}
                                                onRetry={() => {
                                                    for (const reportId of compareSelectedIds) {
                                                        void loadReportDetail(
                                                            reportId,
                                                        );
                                                    }
                                                }}
                                            />
                                        )}
                                        <div className="flex flex-col gap-2">
                                            <div className="text-foreground text-xs font-semibold">
                                                Trends
                                            </div>
                                            {compareSelectedReports.length ===
                                            0 ? (
                                                <div className="text-muted-foreground text-sm">
                                                    Select reports to view chart
                                                    trends.
                                                </div>
                                            ) : compareChartsLoading ? (
                                                <div className="text-muted-foreground flex items-center gap-2 text-sm">
                                                    <Spinner className="size-4" />
                                                    Loading charts...
                                                </div>
                                            ) : compareChartsHaveData ? (
                                                <div className="grid gap-4 @lg/main:grid-cols-2">
                                                    <div className="rounded-md border p-3">
                                                        <div className="text-muted-foreground text-xs">
                                                            Pass rate
                                                        </div>
                                                        <ChartContainer
                                                            className="aspect-auto h-[220px] w-full"
                                                            config={
                                                                passRateChartConfig
                                                            }
                                                        >
                                                            <BarChart
                                                                data={
                                                                    compareChartData
                                                                }
                                                            >
                                                                <CartesianGrid
                                                                    vertical={
                                                                        false
                                                                    }
                                                                />
                                                                <XAxis
                                                                    angle={-20}
                                                                    axisLine={
                                                                        false
                                                                    }
                                                                    dataKey="label"
                                                                    height={60}
                                                                    interval={0}
                                                                    textAnchor="end"
                                                                    tickLine={
                                                                        false
                                                                    }
                                                                    tickMargin={
                                                                        8
                                                                    }
                                                                />
                                                                <YAxis
                                                                    axisLine={
                                                                        false
                                                                    }
                                                                    domain={[
                                                                        0, 1,
                                                                    ]}
                                                                    tickFormatter={(
                                                                        value,
                                                                    ) =>
                                                                        `${Math.round(value * 100)}%`
                                                                    }
                                                                    tickLine={
                                                                        false
                                                                    }
                                                                    width={48}
                                                                />
                                                                <ChartTooltip
                                                                    content={
                                                                        <CompareChartTooltip metric="passRate" />
                                                                    }
                                                                    cursor={
                                                                        false
                                                                    }
                                                                />
                                                                <Bar
                                                                    dataKey="passRate"
                                                                    fill="var(--color-passRate)"
                                                                    radius={4}
                                                                />
                                                            </BarChart>
                                                        </ChartContainer>
                                                    </div>
                                                    <div className="rounded-md border p-3">
                                                        <div className="text-muted-foreground text-xs">
                                                            Median duration
                                                        </div>
                                                        <ChartContainer
                                                            className="aspect-auto h-[220px] w-full"
                                                            config={
                                                                durationChartConfig
                                                            }
                                                        >
                                                            <BarChart
                                                                data={
                                                                    compareChartData
                                                                }
                                                            >
                                                                <CartesianGrid
                                                                    vertical={
                                                                        false
                                                                    }
                                                                />
                                                                <XAxis
                                                                    angle={-20}
                                                                    axisLine={
                                                                        false
                                                                    }
                                                                    dataKey="label"
                                                                    height={60}
                                                                    interval={0}
                                                                    textAnchor="end"
                                                                    tickLine={
                                                                        false
                                                                    }
                                                                    tickMargin={
                                                                        8
                                                                    }
                                                                />
                                                                <YAxis
                                                                    axisLine={
                                                                        false
                                                                    }
                                                                    tickFormatter={(
                                                                        value: number,
                                                                    ) =>
                                                                        `${value.toFixed(2)}s`
                                                                    }
                                                                    tickLine={
                                                                        false
                                                                    }
                                                                    width={56}
                                                                />
                                                                <ChartTooltip
                                                                    content={
                                                                        <CompareChartTooltip metric="duration" />
                                                                    }
                                                                    cursor={
                                                                        false
                                                                    }
                                                                />
                                                                <Bar
                                                                    dataKey="duration"
                                                                    fill="var(--color-duration)"
                                                                    radius={4}
                                                                />
                                                            </BarChart>
                                                        </ChartContainer>
                                                    </div>
                                                </div>
                                            ) : (
                                                <div className="text-muted-foreground text-sm">
                                                    No summary data available
                                                    for the selected reports.
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                )}
                            </CardContent>
                        </>
                    ) : (
                        <>
                            <CardHeader className="gap-3">
                                <div className="flex flex-wrap items-center justify-between gap-2">
                                    <div>
                                        <CardTitle>Models</CardTitle>
                                        <CardDescription>
                                            {compareType ??
                                                "Select a report type to view model groups."}
                                        </CardDescription>
                                    </div>
                                    <ToggleGroup
                                        onValueChange={(value) => {
                                            if (
                                                value === "report" ||
                                                value === "compare" ||
                                                value === "trends" ||
                                                value === "models"
                                            ) {
                                                setViewMode(value);
                                            }
                                        }}
                                        size="sm"
                                        type="single"
                                        value={viewMode}
                                        variant="outline"
                                    >
                                        <ToggleGroupItem value="report">
                                            Report
                                        </ToggleGroupItem>
                                        <ToggleGroupItem value="compare">
                                            Compare
                                        </ToggleGroupItem>
                                        <ToggleGroupItem value="trends">
                                            Trends
                                        </ToggleGroupItem>
                                        <ToggleGroupItem value="models">
                                            Models
                                        </ToggleGroupItem>
                                    </ToggleGroup>
                                </div>
                            </CardHeader>
                            <CardContent className="min-h-[240px]">
                                {compareTypeOptions.length === 0 ? (
                                    <div className="text-muted-foreground text-sm">
                                        No eval reports are available to group
                                        yet.
                                    </div>
                                ) : (
                                    <div className="flex flex-col gap-4">
                                        <div className="grid gap-3 @lg/main:grid-cols-[1fr]">
                                            <div className="flex flex-col gap-1">
                                                <Label className="text-muted-foreground text-xs">
                                                    Type
                                                </Label>
                                                <Select
                                                    onValueChange={(value) => {
                                                        setCompareType(value);
                                                    }}
                                                    value={compareType}
                                                >
                                                    <SelectTrigger className="w-full">
                                                        <SelectValue placeholder="Select type" />
                                                    </SelectTrigger>
                                                    <SelectContent>
                                                        {compareTypeOptions.map(
                                                            (type) => (
                                                                <SelectItem
                                                                    key={type}
                                                                    value={type}
                                                                >
                                                                    {type}
                                                                </SelectItem>
                                                            ),
                                                        )}
                                                    </SelectContent>
                                                </Select>
                                            </div>
                                        </div>
                                        {detailError !== undefined && (
                                            <InlineError
                                                message={detailError}
                                                onRetry={() => {
                                                    for (const report of compareGroupReports) {
                                                        if (
                                                            reportDetails[
                                                                report.id
                                                            ] === undefined
                                                        ) {
                                                            void loadReportDetail(
                                                                report.id,
                                                            );
                                                        }
                                                    }
                                                }}
                                            />
                                        )}
                                        <div className="flex flex-col gap-2">
                                            <div className="text-foreground text-xs font-semibold">
                                                Model groups
                                            </div>
                                            {modelGroupsLoading ? (
                                                <div className="text-muted-foreground flex items-center gap-2 text-sm">
                                                    <Spinner className="size-4" />
                                                    Loading model groups...
                                                </div>
                                            ) : modelGroups.entries.length ===
                                              0 ? (
                                                <div className="text-muted-foreground text-sm">
                                                    No model group data
                                                    available for the selected
                                                    type.
                                                </div>
                                            ) : (
                                                <div className="overflow-x-auto">
                                                    <Table>
                                                        <TableHeader>
                                                            <TableRow>
                                                                <TableHead>
                                                                    Model combo
                                                                </TableHead>
                                                                <TableHead className="text-right">
                                                                    Reports
                                                                </TableHead>
                                                                <TableHead className="text-right">
                                                                    Median pass
                                                                    rate
                                                                </TableHead>
                                                                <TableHead className="text-right">
                                                                    Median
                                                                    median
                                                                    duration
                                                                </TableHead>
                                                            </TableRow>
                                                        </TableHeader>
                                                        <TableBody>
                                                            {modelGroups.entries.map(
                                                                (entry) => {
                                                                    const isSelected =
                                                                        entry.key ===
                                                                        modelGroupKey;
                                                                    return (
                                                                        <TableRow
                                                                            className={`hover:bg-muted/50 cursor-pointer ${
                                                                                isSelected
                                                                                    ? "bg-muted/50"
                                                                                    : ""
                                                                            }`}
                                                                            key={
                                                                                entry.key
                                                                            }
                                                                            onClick={() => {
                                                                                setModelGroupKey(
                                                                                    entry.key,
                                                                                );
                                                                            }}
                                                                        >
                                                                            <TableCell className="text-xs break-words">
                                                                                {
                                                                                    entry.label
                                                                                }
                                                                            </TableCell>
                                                                            <TableCell className="text-right tabular-nums">
                                                                                {
                                                                                    entry
                                                                                        .reports
                                                                                        .length
                                                                                }
                                                                            </TableCell>
                                                                            <TableCell className="text-right tabular-nums">
                                                                                {formatPercentValue(
                                                                                    entry.passRateMedian,
                                                                                )}
                                                                            </TableCell>
                                                                            <TableCell className="text-right tabular-nums">
                                                                                {formatDurationValue(
                                                                                    entry.durationMedian,
                                                                                )}
                                                                            </TableCell>
                                                                        </TableRow>
                                                                    );
                                                                },
                                                            )}
                                                        </TableBody>
                                                    </Table>
                                                </div>
                                            )}
                                        </div>
                                        <div className="flex flex-col gap-2">
                                            <div className="text-foreground text-xs font-semibold">
                                                Reports
                                            </div>
                                            {selectedModelGroup ===
                                            undefined ? (
                                                <div className="text-muted-foreground text-sm">
                                                    Select a model combo to view
                                                    reports.
                                                </div>
                                            ) : selectedModelGroup.reports
                                                  .length === 0 ? (
                                                <div className="text-muted-foreground text-sm">
                                                    No reports are available for
                                                    the selected combo.
                                                </div>
                                            ) : (
                                                <div className="overflow-x-auto">
                                                    <Table>
                                                        <TableHeader>
                                                            <TableRow>
                                                                <TableHead>
                                                                    Generated
                                                                </TableHead>
                                                                <TableHead>
                                                                    Report
                                                                </TableHead>
                                                                <TableHead className="text-right">
                                                                    Pass rate
                                                                </TableHead>
                                                                <TableHead className="text-right">
                                                                    Median
                                                                    duration
                                                                </TableHead>
                                                            </TableRow>
                                                        </TableHeader>
                                                        <TableBody>
                                                            {selectedModelGroup.reports.map(
                                                                (report) => {
                                                                    const metrics =
                                                                        selectedModelGroupMetrics.get(
                                                                            report.id,
                                                                        );
                                                                    return (
                                                                        <TableRow
                                                                            className="hover:bg-muted/50 cursor-pointer"
                                                                            key={
                                                                                report.id
                                                                            }
                                                                            onClick={() => {
                                                                                setSelectedReportId(
                                                                                    report.id,
                                                                                );
                                                                                setViewMode(
                                                                                    "report",
                                                                                );
                                                                            }}
                                                                        >
                                                                            <TableCell className="text-xs">
                                                                                {formatTimestamp(
                                                                                    report.generatedAt,
                                                                                )}
                                                                            </TableCell>
                                                                            <TableCell className="text-xs break-words">
                                                                                {
                                                                                    report.filename
                                                                                }
                                                                            </TableCell>
                                                                            <TableCell className="text-right tabular-nums">
                                                                                {formatPercentValue(
                                                                                    metrics?.passRate,
                                                                                )}
                                                                            </TableCell>
                                                                            <TableCell className="text-right tabular-nums">
                                                                                {formatDurationValue(
                                                                                    metrics?.duration,
                                                                                )}
                                                                            </TableCell>
                                                                        </TableRow>
                                                                    );
                                                                },
                                                            )}
                                                        </TableBody>
                                                    </Table>
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                )}
                            </CardContent>
                        </>
                    )}
                </Card>
            </PageSection>
        </PageShell>
    );
};
