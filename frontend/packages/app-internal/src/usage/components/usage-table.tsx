import { Badge } from "@va/shared/components/ui/badge";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@va/shared/components/ui/card";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@va/shared/components/ui/table";
import type { JSX } from "react";

import type { ChatCompletionTraceBasic } from "../types";

interface UsageTableProps {
    traces: ChatCompletionTraceBasic[];
}

const formatCost = (cost: number | null): string => {
    if (cost === null) {
        return "-";
    }
    if (cost === 0) {
        return "$0.00";
    }
    if (cost > 0 && cost < 0.0001) {
        return "<$0.0001";
    }
    return cost < 0.01 ? `$${cost.toFixed(4)}` : `$${cost.toFixed(2)}`;
};

const formatDuration = (seconds: number | null): string => {
    if (seconds === null) {
        return "-";
    }
    return seconds < 1
        ? `${Math.round(seconds * 1000)}ms`
        : `${seconds.toFixed(2)}s`;
};

const formatTimestamp = (value: string): string =>
    new Date(value).toLocaleString("en-US", {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    });

const formatPlatform = (value: boolean | null): string => {
    if (value === true) {
        return "Public";
    }
    if (value === false) {
        return "Internal";
    }
    return "Unknown";
};

export const UsageTable = ({ traces }: UsageTableProps): JSX.Element => (
    <Card className="@container/card">
        <CardHeader>
            <CardTitle>Recent requests</CardTitle>
            <CardDescription>Latest {traces.length} requests</CardDescription>
        </CardHeader>
        <CardContent className="overflow-hidden px-0">
            <div className="overflow-x-auto px-6">
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableHead>Time</TableHead>
                            <TableHead>Model</TableHead>
                            <TableHead>Platform</TableHead>
                            <TableHead className="text-right">Tokens</TableHead>
                            <TableHead className="text-right">Cost</TableHead>
                            <TableHead className="text-right">
                                Duration
                            </TableHead>
                            <TableHead>Status</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {traces.length === 0 ? (
                            <TableRow>
                                <TableCell colSpan={7}>
                                    No usage data available yet.
                                </TableCell>
                            </TableRow>
                        ) : (
                            traces.map((trace) => {
                                const totalTokens =
                                    (trace.prompt_tokens ?? 0) +
                                    (trace.completion_tokens ?? 0);

                                return (
                                    <TableRow key={trace.created_at}>
                                        <TableCell>
                                            {formatTimestamp(trace.created_at)}
                                        </TableCell>
                                        <TableCell>{trace.model}</TableCell>
                                        <TableCell>
                                            {formatPlatform(trace.is_public)}
                                        </TableCell>
                                        <TableCell className="text-right tabular-nums">
                                            {totalTokens.toLocaleString()}
                                        </TableCell>
                                        <TableCell className="text-right tabular-nums">
                                            {formatCost(trace.cost)}
                                        </TableCell>
                                        <TableCell className="text-right tabular-nums">
                                            {formatDuration(trace.duration)}
                                        </TableCell>
                                        <TableCell>
                                            <Badge
                                                variant={
                                                    trace.is_error
                                                        ? "destructive"
                                                        : "secondary"
                                                }
                                            >
                                                {trace.is_error
                                                    ? "Error"
                                                    : "OK"}
                                            </Badge>
                                        </TableCell>
                                    </TableRow>
                                );
                            })
                        )}
                    </TableBody>
                </Table>
            </div>
        </CardContent>
    </Card>
);
