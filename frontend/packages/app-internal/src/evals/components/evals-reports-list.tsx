import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@va/shared/components/ui/card";
import { Input } from "@va/shared/components/ui/input";
import type { JSX } from "react";

import { formatOptionalNumber, formatTimestamp } from "../lib/report-utils";
import type { EvalReportSummary } from "../types";

interface EvalsReportsListProps {
    listDescription: string;
    searchValue: string;
    onSearchChange: (value: string) => void;
    filteredReports: EvalReportSummary[];
    selectedReportId?: string;
    onSelectReport: (reportId: string) => void;
}

export const EvalsReportsList = ({
    listDescription,
    searchValue,
    onSearchChange,
    filteredReports,
    selectedReportId,
    onSelectReport,
}: EvalsReportsListProps): JSX.Element => (
    <Card>
        <CardHeader className="gap-4">
            <div>
                <CardTitle>Reports</CardTitle>
                <CardDescription>{listDescription}</CardDescription>
            </div>
            <Input
                onChange={(event) => {
                    onSearchChange(event.target.value);
                }}
                placeholder="Search reports"
                value={searchValue}
            />
        </CardHeader>
        <CardContent className="px-0">
            <div className="px-6">
                {filteredReports.length === 0 ? (
                    <div className="text-muted-foreground text-sm">
                        No reports match your search.
                    </div>
                ) : (
                    <div className="divide-border divide-y">
                        {filteredReports.map((report) => (
                            <button
                                className="hover:bg-muted/50 data-[state=selected]:bg-muted flex w-full flex-col gap-2 px-3 py-3 text-left transition-colors"
                                data-state={
                                    selectedReportId === report.id
                                        ? "selected"
                                        : undefined
                                }
                                key={report.id}
                                onClick={() => {
                                    onSelectReport(report.id);
                                }}
                                type="button"
                            >
                                <div className="flex flex-col gap-1">
                                    <span className="font-medium break-words">
                                        {report.name}
                                    </span>
                                    <span className="text-muted-foreground text-xs break-words">
                                        {report.filename}
                                    </span>
                                </div>
                                <div className="text-muted-foreground flex flex-col gap-1 text-xs">
                                    <span>
                                        Generated{" "}
                                        {formatTimestamp(report.generatedAt)}
                                    </span>
                                    <div className="flex flex-wrap gap-2">
                                        <span className="tabular-nums">
                                            Repeats{" "}
                                            {formatOptionalNumber(
                                                report.repeats,
                                            )}
                                        </span>
                                        <span className="text-muted-foreground">
                                            •
                                        </span>
                                        <span className="tabular-nums">
                                            Concurrency{" "}
                                            {formatOptionalNumber(
                                                report.concurrency,
                                            )}
                                        </span>
                                    </div>
                                </div>
                            </button>
                        ))}
                    </div>
                )}
            </div>
        </CardContent>
    </Card>
);
