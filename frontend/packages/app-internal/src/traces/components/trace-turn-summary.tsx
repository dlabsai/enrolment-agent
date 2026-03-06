import {
    ResizableHandle,
    ResizablePanel,
    ResizablePanelGroup,
} from "@va/shared/components/ui/resizable";
import { Toggle } from "@va/shared/components/ui/toggle";
import { type JSX, useMemo, useState } from "react";

import {
    isRecord,
    parseJsonRecursively,
    type TraceMessage,
    type TraceMessagePart,
} from "../lib/trace-utils";
import type { TraceSpan } from "../types";
import { JsonValue } from "./trace-turn-content";
import {
    renderMarkdownValue,
    renderPlainTextValue,
    renderStructuredValue,
} from "./trace-turn-content-utils";
import {
    buildMessageKey,
    buildMessagePartKey,
    getStringField,
} from "./trace-turn-message-utils";
import { buildSpanOverviewModel } from "./trace-turn-summary-model";

interface TraceTurnSummaryProps {
    spans: TraceSpan[];
    traceStart: number | undefined;
    traceEnd: number | undefined;
    summaryLayout?: "stack" | "split";
}

const resolveToolName = (raw: Record<string, unknown> | undefined): string => {
    if (!raw) {
        return "tool";
    }
    const functionData = isRecord(raw.function) ? raw.function : undefined;
    return (
        getStringField(raw, "name") ??
        getStringField(raw, "tool_name") ??
        getStringField(raw, "tool") ??
        (functionData ? getStringField(functionData, "name") : undefined) ??
        "tool"
    );
};

const renderToolCallPart = (part: TraceMessagePart): JSX.Element => {
    const raw = isRecord(part.raw) ? part.raw : undefined;
    const name = resolveToolName(raw);
    const functionData =
        raw && isRecord(raw.function) ? raw.function : undefined;
    const argumentsValue =
        raw === undefined
            ? {}
            : (raw.arguments ??
              (functionData ? functionData.arguments : undefined) ??
              raw.args ??
              raw.input ??
              {});
    const parsedArguments = parseJsonRecursively(argumentsValue);

    return (
        <div className="space-y-2">
            <div className="text-xs font-semibold uppercase">Tool call</div>
            <div className="text-sm font-semibold">{name}</div>
            {renderStructuredValue(parsedArguments)}
        </div>
    );
};

const renderToolResultPart = (part: TraceMessagePart): JSX.Element => {
    const raw = isRecord(part.raw) ? part.raw : undefined;
    const name = resolveToolName(raw);
    const resultValue =
        raw === undefined
            ? (part.content ?? "-")
            : (raw.result ??
              raw.output ??
              raw.response ??
              raw.content ??
              raw.value ??
              raw.data ??
              part.content ??
              "-");
    const parsedResult = parseJsonRecursively(resultValue);

    return (
        <div className="space-y-2">
            <div className="text-xs font-semibold uppercase">Tool result</div>
            <div className="text-sm font-semibold">{name}</div>
            {renderStructuredValue(parsedResult)}
        </div>
    );
};

const renderSummaryToolValue = (value: unknown): JSX.Element => (
    <div className="bg-muted/30 rounded-md border p-2 text-xs">
        <JsonValue value={parseJsonRecursively(value)} />
    </div>
);

const renderSummaryToolCallPart = (
    part: TraceMessagePart,
    showToolName: boolean,
): JSX.Element => {
    const raw = isRecord(part.raw) ? part.raw : undefined;
    const name = resolveToolName(raw);
    const functionData =
        raw && isRecord(raw.function) ? raw.function : undefined;
    const argumentsValue =
        raw === undefined
            ? {}
            : (raw.arguments ??
              (functionData ? functionData.arguments : undefined) ??
              raw.args ??
              raw.input ??
              {});

    return showToolName ? (
        <div className="space-y-1">
            <div className="text-xs font-semibold">{name}</div>
            {renderSummaryToolValue(argumentsValue)}
        </div>
    ) : (
        renderSummaryToolValue(argumentsValue)
    );
};

const renderSummaryToolResultPart = (
    part: TraceMessagePart,
    showToolName: boolean,
): JSX.Element => {
    const raw = isRecord(part.raw) ? part.raw : undefined;
    const name = resolveToolName(raw);
    const resultValue =
        raw === undefined
            ? (part.content ?? "-")
            : (raw.result ??
              raw.output ??
              raw.response ??
              raw.content ??
              raw.value ??
              raw.data ??
              part.content ??
              "-");

    return showToolName ? (
        <div className="space-y-1">
            <div className="text-xs font-semibold">{name}</div>
            {renderSummaryToolValue(resultValue)}
        </div>
    ) : (
        renderSummaryToolValue(resultValue)
    );
};

const renderSummaryToolMessage = (message: TraceMessage): JSX.Element =>
    renderSummaryToolValue(message.content);

const renderSummaryMessageContent = (
    message: TraceMessage,
    formatted: boolean,
    showToolName: boolean,
): JSX.Element => {
    const parts = message.parts ?? [];
    if (parts.length === 0) {
        if (message.role === "tool") {
            return formatted
                ? renderSummaryToolMessage(message)
                : renderStructuredValue(parseJsonRecursively(message.content));
        }
        return formatted
            ? renderMarkdownValue(message.content)
            : renderPlainTextValue(message.content);
    }

    return (
        <div className="space-y-2">
            {parts.map((part) =>
                formatted ? (
                    <div
                        className="space-y-1"
                        key={buildMessagePartKey(part)}
                    >
                        {part.type === "tool_call" ? (
                            showToolName ? (
                                <>
                                    <div className="text-muted-foreground text-xs uppercase">
                                        {part.type}
                                    </div>
                                    {renderSummaryToolCallPart(part, true)}
                                </>
                            ) : (
                                renderSummaryToolCallPart(part, false)
                            )
                        ) : part.type === "tool_result" ||
                          part.type === "tool_call_response" ? (
                            showToolName ? (
                                <>
                                    <div className="text-muted-foreground text-xs uppercase">
                                        {part.type}
                                    </div>
                                    {renderSummaryToolResultPart(part, true)}
                                </>
                            ) : (
                                renderSummaryToolResultPart(part, false)
                            )
                        ) : (
                            <>
                                <div className="text-muted-foreground text-xs uppercase">
                                    {part.type}
                                </div>
                                {renderMarkdownValue(part.content ?? part.raw)}
                            </>
                        )}
                    </div>
                ) : (
                    <div
                        className="space-y-1"
                        key={buildMessagePartKey(part)}
                    >
                        <div className="text-muted-foreground text-xs uppercase">
                            {part.type}
                        </div>
                        {part.type === "tool_call"
                            ? renderToolCallPart(part)
                            : part.type === "tool_result" ||
                                part.type === "tool_call_response"
                              ? renderToolResultPart(part)
                              : renderPlainTextValue(part.content ?? part.raw)}
                    </div>
                ),
            )}
        </div>
    );
};

export const TraceTurnSummary = ({
    spans,
    traceStart,
    traceEnd,
    summaryLayout = "stack",
}: TraceTurnSummaryProps): JSX.Element => {
    const [summaryFormatted, setSummaryFormatted] = useState(
        () => summaryLayout === "split",
    );
    const [selectedTimingSpanId, setSelectedTimingSpanId] = useState<
        string | undefined
    >();

    const overviewModel = useMemo(
        () =>
            buildSpanOverviewModel({
                spans,
                traceStart,
                traceEnd,
                selectedSpanId: selectedTimingSpanId,
            }),
        [selectedTimingSpanId, spans, traceEnd, traceStart],
    );
    const { timingRows } = overviewModel;
    const { selection } = overviewModel;
    const hasSelectedSpan = selection !== undefined;
    const requestMessages = selection?.requestMessages ?? [];
    const responseMessages = selection?.responseMessages ?? [];
    const hasSummaryContent = selection?.hasSummaryContent ?? false;
    const requestLabel = selection?.requestLabel;
    const responseLabel = selection?.responseLabel;
    const showToolName = selection?.showToolName ?? false;
    const isEmbeddings = selection?.isEmbeddings ?? false;
    const headerRows = selection?.headerRows ?? [];

    const renderMessageList = (
        messages: TraceMessage[],
        includeToolNames: boolean,
    ): JSX.Element => (
        <div className="space-y-3">
            {messages.map((message) => {
                const parts = message.parts ?? [];
                const isToolOnlyMessage =
                    message.role === "tool" ||
                    (parts.length > 0 &&
                        parts.every(
                            (part) =>
                                part.type === "tool_call" ||
                                part.type === "tool_result" ||
                                part.type === "tool_call_response",
                        ));
                return (
                    <div
                        className="border-muted space-y-1 border-l pl-3"
                        key={`summary-message-${buildMessageKey(message)}`}
                    >
                        {isToolOnlyMessage ? undefined : (
                            <div className="text-muted-foreground text-xs uppercase">
                                {message.role}
                            </div>
                        )}
                        {renderSummaryMessageContent(
                            message,
                            summaryFormatted,
                            includeToolNames,
                        )}
                    </div>
                );
            })}
        </div>
    );

    const timingList = (
        <div className="space-y-2 text-xs">
            {timingRows.map((entry) => {
                const isSelected = entry.spanId === selectedTimingSpanId;
                return (
                    <button
                        className={`hover:bg-muted/60 grid w-full grid-cols-[140px_70px_1fr] items-center gap-x-3 rounded px-1 py-0.5 text-left transition ${
                            isSelected ? "bg-muted/70" : ""
                        }`}
                        key={entry.spanId}
                        onClick={() => {
                            setSelectedTimingSpanId((previous) =>
                                previous === entry.spanId
                                    ? undefined
                                    : entry.spanId,
                            );
                        }}
                        type="button"
                    >
                        <div className="font-semibold">{entry.label}</div>
                        <div className="text-muted-foreground tabular-nums">
                            {entry.value}
                        </div>
                        <div className="bg-muted relative h-2 overflow-hidden rounded">
                            <div
                                className={`absolute inset-y-0 rounded ${entry.barClass}`}
                                style={{
                                    left: `${entry.offsetPct}%`,
                                    width: `${entry.widthPct}%`,
                                }}
                            />
                        </div>
                    </button>
                );
            })}
        </div>
    );

    const renderSummarySection = (
        label: string | undefined,
        messages: TraceMessage[],
        emptyLabel: string,
    ): JSX.Element => (
        <section className="space-y-2">
            {label !== undefined && label.trim() !== "" ? (
                <h3 className="text-xs font-semibold uppercase">{label}</h3>
            ) : undefined}
            {messages.length > 0 ? (
                renderMessageList(messages, showToolName)
            ) : (
                <div className="text-muted-foreground text-xs">
                    {emptyLabel}
                </div>
            )}
        </section>
    );

    const summaryDetails = (
        <div className="space-y-4">
            {hasSelectedSpan ? (
                <div className="space-y-1 text-xs">
                    {headerRows.map((entry) => (
                        <div
                            className="grid grid-cols-[140px_1fr] items-center gap-x-3"
                            key={`selected-${entry.label}`}
                        >
                            <div className="font-semibold">{entry.label}</div>
                            <div className="text-muted-foreground">
                                {entry.value}
                            </div>
                        </div>
                    ))}
                </div>
            ) : (
                <div className="text-muted-foreground text-xs">
                    Select a span to view request/response details.
                </div>
            )}
            {hasSelectedSpan ? (
                hasSummaryContent ? (
                    <div className="space-y-4 text-sm">
                        {renderSummarySection(
                            requestLabel,
                            requestMessages,
                            "No request content for this span.",
                        )}
                        {isEmbeddings && responseMessages.length === 0
                            ? undefined
                            : renderSummarySection(
                                  responseLabel,
                                  responseMessages,
                                  "No response content for this span.",
                              )}
                    </div>
                ) : (
                    <div className="text-muted-foreground text-xs">
                        Select a span with request/response details.
                    </div>
                )
            ) : undefined}
        </div>
    );

    const summaryStack = (
        <section className="space-y-3">
            {timingList}
            {summaryDetails}
        </section>
    );

    const summarySplit = (
        <ResizablePanelGroup
            className="h-full min-h-0 min-w-0"
            direction="horizontal"
        >
            <ResizablePanel
                className="min-h-0 min-w-0"
                defaultSize={38}
                minSize={30}
            >
                <div className="h-full min-h-0 min-w-0 overflow-auto">
                    <div className="space-y-3 px-4 py-4">
                        <div className="text-muted-foreground text-xs uppercase">
                            Timeline
                        </div>
                        {timingList}
                    </div>
                </div>
            </ResizablePanel>
            <ResizableHandle withHandle />
            <ResizablePanel
                className="min-h-0 min-w-0"
                defaultSize={62}
                minSize={40}
            >
                <div className="h-full min-h-0 min-w-0 overflow-auto">
                    <div className="space-y-4 px-4 py-4">
                        <div className="flex items-center justify-end gap-3">
                            <Toggle
                                onPressedChange={setSummaryFormatted}
                                pressed={summaryFormatted}
                                size="sm"
                                variant="outline"
                            >
                                {summaryFormatted ? "Formatted" : "Plain"}
                            </Toggle>
                        </div>
                        {summaryDetails}
                    </div>
                </div>
            </ResizablePanel>
        </ResizablePanelGroup>
    );

    return summaryLayout === "split" ? (
        summarySplit
    ) : (
        <div className="h-full min-h-0 min-w-0 overflow-auto">
            <div className="space-y-6 px-4 py-4">{summaryStack}</div>
        </div>
    );
};
