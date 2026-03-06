import { useNavigate, useParams, useSearch } from "@tanstack/react-router";
import { Badge } from "@va/shared/components/ui/badge";
import { Button } from "@va/shared/components/ui/button";
import { RefreshCw } from "lucide-react";
import { type JSX, useCallback, useMemo } from "react";

import { PageHeader } from "../../components/page-header";
import { PageSection, PageShell } from "../../components/page-shell";
import { useTraceDetail } from "../hooks/use-trace-detail";
import {
    formatDurationMs,
    formatPlatform,
    formatTimestamp,
} from "../lib/trace-utils";
import { TraceDetailPanel } from "./trace-detail-panel";

const formatTraceId = (traceId: string): string => traceId;

export const TraceDetailPage = (): JSX.Element => {
    const { traceId } = useParams({ from: "/traces/$traceId" });
    const search = useSearch({ from: "/traces/$traceId" });
    const navigate = useNavigate({ from: "/traces/$traceId" });

    const { detail, loading, error, refresh } = useTraceDetail(traceId);

    const detailTitle = `Trace ${formatTraceId(traceId)}`;
    const detailDescription = useMemo(() => {
        if (!detail) {
            return "Trace details";
        }
        return (
            <span className="inline-flex flex-wrap items-center gap-2">
                <Badge
                    variant={
                        detail.is_public === true ? "secondary" : "outline"
                    }
                >
                    {formatPlatform(detail.is_public)}
                </Badge>
                <span>{formatTimestamp(detail.started_at)}</span>
                <span>{formatDurationMs(detail.duration_ms)}</span>
                <span>{detail.span_count} spans</span>
            </span>
        );
    }, [detail]);

    const handleSpanChange = useCallback(
        (spanId: string | undefined): void => {
            void navigate({
                params: { traceId },
                search: (prev) => ({
                    ...prev,
                    span: spanId,
                }),
                to: "/traces/$traceId",
            });
        },
        [navigate, traceId],
    );

    const handleSpanSync = useCallback(
        (spanId: string | undefined): void => {
            void navigate({
                params: { traceId },
                replace: true,
                search: (prev) => ({
                    ...prev,
                    span: spanId,
                }),
                to: "/traces/$traceId",
            });
        },
        [navigate, traceId],
    );

    return (
        <PageShell
            className="overflow-hidden"
            variant="dashboard"
        >
            <PageHeader title={detailTitle}>
                <div className="ml-auto flex items-center gap-2">
                    <Button
                        onClick={() => void refresh()}
                        size="sm"
                        variant="outline"
                    >
                        <RefreshCw className="mr-2 size-4" />
                        Refresh
                    </Button>
                </div>
            </PageHeader>

            <PageSection className="flex min-h-0 flex-1 flex-col gap-4">
                <div className="text-muted-foreground text-sm">
                    {detailDescription}
                </div>
                <div className="min-h-0 flex-1 overflow-hidden">
                    <TraceDetailPanel
                        detail={detail}
                        error={error}
                        loading={loading}
                        onSpanChange={handleSpanChange}
                        onSpanSync={handleSpanSync}
                        selectedSpanId={search.span}
                    />
                </div>
            </PageSection>
        </PageShell>
    );
};
