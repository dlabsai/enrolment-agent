import {
    ResizableHandle,
    ResizablePanel,
    ResizablePanelGroup,
} from "@va/shared/components/ui/resizable";
import { Info } from "lucide-react";
import { type JSX, memo, useCallback, useMemo, useRef, useState } from "react";

import { PageLoading } from "@/components/page-state";

import { getSpanEnd, getSpanStart } from "../lib/trace-utils";
import type { TraceDetail } from "../types";
import { SpanNavigator } from "./trace-turn-span-navigator";
import { SpanSection } from "./trace-turn-span-section";
import {
    buildSpanSections,
    type SpanSectionMeta,
} from "./trace-turn-span-section-utils";
import { TraceTurnSummary } from "./trace-turn-summary";

interface TraceTurnDebugViewProps {
    detail: TraceDetail | undefined;
    loading: boolean;
    error: string | undefined;
    summaryOnly?: boolean;
    summaryLayout?: "stack" | "split";
}

export const TraceTurnDebugView = memo(
    ({
        detail,
        loading,
        error,
        summaryOnly = false,
        summaryLayout = "stack",
    }: TraceTurnDebugViewProps): JSX.Element => {
        const spans = useMemo(() => detail?.spans ?? [], [detail]);
        const spanSections = useMemo(() => buildSpanSections(spans), [spans]);
        const selectedSpanIdDefault = spanSections[0]?.span.span_id;
        const [selectedSpanId, setSelectedSpanId] = useState<
            string | undefined
        >(selectedSpanIdDefault);
        const scrollRef = useRef<HTMLDivElement | null>(null);

        const resolvedSelectedSpanId = useMemo(() => {
            if (
                selectedSpanId !== undefined &&
                spanSections.some(
                    (entry) => entry.span.span_id === selectedSpanId,
                )
            ) {
                return selectedSpanId;
            }
            return selectedSpanIdDefault;
        }, [selectedSpanId, selectedSpanIdDefault, spanSections]);

        const spanStartTimes = spans
            .map((span) => getSpanStart(span))
            .filter((value): value is number => value !== undefined);
        const traceStart =
            spanStartTimes.length > 0 ? Math.min(...spanStartTimes) : undefined;
        const spanEndTimes = spans
            .map((span) => getSpanEnd(span))
            .filter((value): value is number => value !== undefined);
        const traceEnd =
            spanEndTimes.length > 0 ? Math.max(...spanEndTimes) : undefined;

        const handleSpanSelect = useCallback(
            (spanId: string): void => {
                setSelectedSpanId(spanId);
                const container = scrollRef.current;
                if (!container) {
                    return;
                }
                const element = container.querySelector(
                    `[data-span-anchor="${spanId}"]`,
                );
                if (element instanceof HTMLElement) {
                    element.scrollIntoView({ block: "start" });
                }
            },
            [scrollRef, setSelectedSpanId],
        );

        let content: JSX.Element = (
            <div className="text-muted-foreground flex h-full items-center justify-center gap-2 text-sm">
                <Info className="size-4" /> Select a trace to view spans
            </div>
        );

        if (loading) {
            content = <PageLoading />;
        } else if (error !== undefined) {
            content = (
                <div className="text-destructive flex h-full items-center justify-center">
                    {error}
                </div>
            );
        } else if (detail !== undefined) {
            content = summaryOnly ? (
                <TraceTurnSummary
                    spans={spans}
                    summaryLayout={summaryLayout}
                    traceEnd={traceEnd}
                    traceStart={traceStart}
                />
            ) : (
                <ResizablePanelGroup
                    className="h-full min-h-0 min-w-0"
                    direction="horizontal"
                >
                    <ResizablePanel
                        className="min-h-0 min-w-0"
                        defaultSize={32}
                        minSize={25}
                    >
                        <SpanNavigator
                            onSelectSpan={handleSpanSelect}
                            selectedSpanId={resolvedSelectedSpanId}
                            spans={spans}
                        />
                    </ResizablePanel>
                    <ResizableHandle withHandle />
                    <ResizablePanel
                        className="min-h-0 min-w-0"
                        defaultSize={68}
                        minSize={40}
                    >
                        <div className="h-full min-h-0 min-w-0 overflow-auto">
                            <div
                                className="space-y-6 px-4 py-4"
                                ref={scrollRef}
                            >
                                {spanSections.length === 0 ? (
                                    <div className="text-muted-foreground text-sm">
                                        No spans recorded for this trace.
                                    </div>
                                ) : (
                                    <div className="space-y-6">
                                        {spanSections.map(
                                            (entry: SpanSectionMeta) => (
                                                <SpanSection
                                                    anchorId={
                                                        entry.span.span_id
                                                    }
                                                    isSelected={
                                                        resolvedSelectedSpanId ===
                                                        entry.span.span_id
                                                    }
                                                    key={entry.span.span_id}
                                                    span={entry.span}
                                                    subtitle={entry.subtitle}
                                                    title={entry.title}
                                                    traceEnd={traceEnd}
                                                    traceStart={traceStart}
                                                />
                                            ),
                                        )}
                                    </div>
                                )}
                            </div>
                        </div>
                    </ResizablePanel>
                </ResizablePanelGroup>
            );
        }

        return <div className="h-full min-h-0 overflow-hidden">{content}</div>;
    },
);
TraceTurnDebugView.displayName = "TraceTurnDebugView";
