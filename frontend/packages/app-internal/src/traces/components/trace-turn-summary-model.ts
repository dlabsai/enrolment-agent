import {
    extractRequestMessages,
    extractResponseMessages,
    extractResponseToolCalls,
    extractToolResults,
    getSpanEnd,
    getSpanStart,
    getStringAttribute,
    type TraceMessage,
    type TraceMessagePart,
} from "../lib/trace-utils";
import { formatSpanDuration } from "../lib/trace-view-utils";
import type { TraceSpan } from "../types";
import { stringifyValue } from "./trace-turn-content-utils";
import {
    formatCost,
    formatNumeric,
    formatOffsetMs,
    getNumericAttribute,
} from "./trace-turn-metrics-utils";

interface TimingRow {
    spanId: string;
    label: string;
    value: string;
    offsetPct: number;
    widthPct: number;
    barClass: string;
    start: number;
}

interface SpanOverviewSelection {
    headerRows: { label: string; value: string }[];
    requestLabel?: string;
    responseLabel?: string;
    requestMessages: TraceMessage[];
    responseMessages: TraceMessage[];
    hasSummaryContent: boolean;
    showToolName: boolean;
    isEmbeddings: boolean;
}

interface SpanOverviewModel {
    timingRows: TimingRow[];
    selection?: SpanOverviewSelection;
}

const resolveAttributeValue = (
    attributes: Record<string, unknown>,
    keys: string[],
): unknown => {
    for (const key of keys) {
        const value = attributes[key];
        const hasValue =
            value !== undefined &&
            value !== null &&
            (typeof value !== "string" || value.trim() !== "");
        if (hasValue) {
            return value;
        }
    }
    return undefined;
};

const buildTokenSummary = (
    inputTokens: number | undefined,
    cacheTokens: number | undefined,
    outputTokens: number | undefined,
    cost: number | undefined,
    isLlm: boolean,
): string | undefined => {
    const parts: string[] = [];
    if (inputTokens !== undefined) {
        parts.push(`input ${formatNumeric(inputTokens)}`);
    }
    if (isLlm && cacheTokens !== undefined) {
        parts.push(`cache ${formatNumeric(cacheTokens)}`);
    }
    if (isLlm && outputTokens !== undefined) {
        parts.push(`output ${formatNumeric(outputTokens)}`);
    }
    if (cost !== undefined) {
        parts.push(`cost ${formatCost(cost)}`);
    }
    return parts.length > 0 ? parts.join(" • ") : undefined;
};

const buildSpanLookup = (spans: TraceSpan[]): Map<string, TraceSpan> => {
    const lookup = new Map<string, TraceSpan>();
    for (const span of spans) {
        lookup.set(span.span_id, span);
    }
    return lookup;
};

const resolveAgentName = (
    span: TraceSpan,
    spanLookup: Map<string, TraceSpan>,
): string | undefined => {
    const direct = getStringAttribute(
        span.attributes ?? {},
        "gen_ai.agent.name",
    );
    if (direct !== undefined && direct.trim() !== "") {
        return direct;
    }

    let parentId: string | undefined = span.parent_span_id ?? undefined;
    const visited = new Set<string>();
    while (typeof parentId === "string" && parentId.trim() !== "") {
        if (visited.has(parentId)) {
            return undefined;
        }
        visited.add(parentId);
        const parent = spanLookup.get(parentId);
        if (parent === undefined) {
            return undefined;
        }
        const agentName = getStringAttribute(
            parent.attributes ?? {},
            "gen_ai.agent.name",
        );
        if (agentName !== undefined && agentName.trim() !== "") {
            return agentName;
        }
        parentId = parent.parent_span_id ?? undefined;
    }
    return undefined;
};

const hasToolAttributes = (attributes: Record<string, unknown>): boolean =>
    attributes["gen_ai.tool.name"] !== undefined ||
    attributes["gen_ai.tool.call"] !== undefined ||
    attributes["gen_ai.tool.calls"] !== undefined ||
    attributes["gen_ai.tool.result"] !== undefined ||
    attributes["gen_ai.tool.results"] !== undefined ||
    attributes["gen_ai.tool.call.name"] !== undefined ||
    attributes["gen_ai.tool.call.arguments"] !== undefined ||
    attributes["gen_ai.tool.call.result"] !== undefined;

const buildTimingRows = (
    sourceSpans: TraceSpan[],
    rangeStart: number | undefined,
    rangeDuration: number | undefined,
    spanLookup: Map<string, TraceSpan>,
): TimingRow[] =>
    sourceSpans
        .map((span): TimingRow | undefined => {
            const attributes = span.attributes ?? {};
            const operationName = getStringAttribute(
                attributes,
                "gen_ai.operation.name",
            );
            const hasOperationName =
                operationName !== undefined && operationName.trim() !== "";
            const isTurnSpan = span.name.includes("handle_conversation_turn");
            const toolName: string | undefined =
                getStringAttribute(attributes, "gen_ai.tool.name") ??
                getStringAttribute(attributes, "gen_ai.tool.call.name");
            const dbSystem: string | undefined = getStringAttribute(
                attributes,
                "db.system",
            );
            const agentName = resolveAgentName(span, spanLookup);
            const agentLabel =
                agentName !== undefined && agentName.trim() !== ""
                    ? agentName.replaceAll("_", " ")
                    : undefined;
            const isSearchDescendant = agentName === "search";
            const hasTool = hasToolAttributes(attributes);

            const isEmbeddings = operationName === "embeddings";
            const isDbSpan = dbSystem !== undefined && isSearchDescendant;
            const isToolSpan = hasTool && isSearchDescendant;
            const isLlmSpan = hasOperationName;

            if (
                !isTurnSpan &&
                !isEmbeddings &&
                !isDbSpan &&
                !isToolSpan &&
                !isLlmSpan
            ) {
                return undefined;
            }

            const start = getSpanStart(span);
            const end = getSpanEnd(span);
            if (
                start === undefined ||
                end === undefined ||
                rangeStart === undefined ||
                rangeDuration === undefined
            ) {
                return undefined;
            }

            const durationMs = end - start;
            const offsetMs = start - rangeStart;
            const offsetPct = Math.max((offsetMs / rangeDuration) * 100, 0);
            const widthPct = Math.max((durationMs / rangeDuration) * 100, 2);

            let label = span.name;
            let barClass = "bg-chart-1";
            if (isTurnSpan) {
                label = "Turn";
                barClass = "bg-primary";
            } else if (isEmbeddings) {
                label = "Embeddings";
                barClass = "bg-chart-3";
            } else if (isToolSpan) {
                const toolLabel =
                    toolName !== undefined && toolName.trim() !== ""
                        ? toolName
                        : span.name;
                label = `Tool: ${toolLabel}`;
                barClass = "bg-chart-5";
            } else if (isDbSpan) {
                label = `DB: ${dbSystem}`;
                barClass = "bg-chart-4";
            } else if (isLlmSpan) {
                label = "LLM";
                switch (agentName) {
                    case "search": {
                        barClass = "bg-chart-2";
                        break;
                    }
                    case "guardrails": {
                        barClass = "bg-chart-4";
                        break;
                    }
                    case "chatbot": {
                        barClass = "bg-chart-1";
                        break;
                    }
                    default: {
                        break;
                    }
                }
            }

            if (agentLabel !== undefined && agentLabel !== "") {
                label = `${agentLabel} · ${label}`;
            }

            return {
                spanId: span.span_id,
                label,
                value: formatSpanDuration(span),
                offsetPct,
                widthPct,
                barClass,
                start,
            };
        })
        .filter((entry): entry is TimingRow => entry !== undefined)
        .toSorted((left, right) => left.start - right.start);

export const buildSpanOverviewModel = ({
    spans,
    traceStart,
    traceEnd,
    selectedSpanId,
}: {
    spans: TraceSpan[];
    traceStart: number | undefined;
    traceEnd: number | undefined;
    selectedSpanId: string | undefined;
}): SpanOverviewModel => {
    const spanLookup = buildSpanLookup(spans);
    const overallRangeStart = traceStart;
    const overallRangeDuration =
        traceStart !== undefined && traceEnd !== undefined
            ? traceEnd - traceStart
            : undefined;

    const timingRows = buildTimingRows(
        spans,
        overallRangeStart,
        overallRangeDuration,
        spanLookup,
    );

    const selectedTimingSpan =
        selectedSpanId === undefined
            ? undefined
            : spanLookup.get(selectedSpanId);
    const selectedTimingAttributes = selectedTimingSpan?.attributes ?? {};
    const selectedSpanName = selectedTimingSpan?.name;
    const selectedAgentName =
        selectedTimingSpan === undefined
            ? undefined
            : resolveAgentName(selectedTimingSpan, spanLookup);
    const selectedSpanLabel =
        selectedSpanName === undefined
            ? undefined
            : selectedAgentName !== undefined && selectedAgentName.trim() !== ""
              ? `${selectedSpanName} (${selectedAgentName.replaceAll("_", " ")})`
              : selectedSpanName;
    const selectedSpanDuration =
        selectedTimingSpan === undefined
            ? undefined
            : formatSpanDuration(selectedTimingSpan);
    const selectedInputTokens = getNumericAttribute(
        selectedTimingAttributes,
        "gen_ai.usage.input_tokens",
    );
    const selectedOutputTokens = getNumericAttribute(
        selectedTimingAttributes,
        "gen_ai.usage.output_tokens",
    );
    const selectedCacheTokens = getNumericAttribute(
        selectedTimingAttributes,
        "gen_ai.usage.details.cache_read_tokens",
    );
    const selectedCost = getNumericAttribute(
        selectedTimingAttributes,
        "operation.cost",
    );
    const selectedSpanStart =
        selectedTimingSpan === undefined
            ? undefined
            : getSpanStart(selectedTimingSpan);
    const selectedOffsetMs =
        traceStart !== undefined && selectedSpanStart !== undefined
            ? selectedSpanStart - traceStart
            : undefined;
    const selectedOperationName = getStringAttribute(
        selectedTimingAttributes,
        "gen_ai.operation.name",
    );
    const hasSelectedOperation =
        selectedOperationName !== undefined &&
        selectedOperationName.trim() !== "";
    const selectedIsEmbeddings = selectedOperationName === "embeddings";
    const selectedIsLlm = hasSelectedOperation && !selectedIsEmbeddings;
    const shouldShowTokens = selectedIsLlm || selectedIsEmbeddings;
    const selectedTokenSummary =
        selectedTimingSpan === undefined || !shouldShowTokens
            ? undefined
            : buildTokenSummary(
                  selectedInputTokens,
                  selectedCacheTokens,
                  selectedOutputTokens,
                  selectedCost,
                  selectedIsLlm,
              );
    const selectedPrompt = resolveAttributeValue(selectedTimingAttributes, [
        "gen_ai.request.prompt",
    ]);
    const selectedEmbeddingInput = resolveAttributeValue(
        selectedTimingAttributes,
        [
            "inputs",
            "gen_ai.request.text",
            "gen_ai.request.input",
            "gen_ai.request.prompt",
        ],
    );
    const selectedRequestMessages = extractRequestMessages(
        selectedTimingAttributes,
    );
    const selectedResponseMessages = extractResponseMessages(
        selectedTimingAttributes,
    );
    const selectedResponseText =
        getStringAttribute(selectedTimingAttributes, "gen_ai.response.text") ??
        getStringAttribute(selectedTimingAttributes, "gen_ai.response.message");
    const selectedToolCalls = extractResponseToolCalls(
        selectedTimingAttributes,
    );
    const selectedToolResults = extractToolResults(selectedTimingAttributes);
    const selectedHasTools =
        hasToolAttributes(selectedTimingAttributes) ||
        selectedToolCalls.length > 0 ||
        selectedToolResults.length > 0;
    const buildToolCallParts = (): TraceMessagePart[] =>
        selectedToolCalls.map((call) => ({
            type: "tool_call",
            content: call.arguments,
            raw: {
                name: call.name,
                arguments: call.arguments,
            },
        }));
    const buildToolResultParts = (): TraceMessagePart[] =>
        selectedToolResults.map((result) => ({
            type: "tool_result",
            content: result.result,
            raw: {
                name: result.name,
                result: result.result,
            },
        }));
    const resolvedRequestMessages: TraceMessage[] =
        selectedIsLlm && selectedRequestMessages.length > 0
            ? selectedRequestMessages
            : selectedIsLlm &&
                selectedPrompt !== undefined &&
                stringifyValue(selectedPrompt).trim() !== ""
              ? [
                    {
                        role: "prompt",
                        content: stringifyValue(selectedPrompt),
                    },
                ]
              : selectedIsEmbeddings &&
                  selectedEmbeddingInput !== undefined &&
                  stringifyValue(selectedEmbeddingInput).trim() !== ""
                ? [
                      {
                          role: "embedding input",
                          content: stringifyValue(selectedEmbeddingInput),
                      },
                  ]
                : selectedHasTools && selectedToolCalls.length > 0
                  ? [
                        {
                            role: "assistant",
                            content: "Tool calls",
                            parts: buildToolCallParts(),
                        },
                    ]
                  : [];
    const resolvedResponseMessages: TraceMessage[] =
        selectedIsLlm && selectedResponseMessages.length > 0
            ? selectedResponseMessages
            : selectedIsLlm &&
                selectedResponseText !== undefined &&
                selectedResponseText.trim() !== ""
              ? [
                    {
                        role: "assistant",
                        content: selectedResponseText,
                    },
                ]
              : selectedHasTools && selectedToolResults.length > 0
                ? [
                      {
                          role: "tool",
                          content: "Tool results",
                          parts: buildToolResultParts(),
                      },
                  ]
                : [];

    const hasSelectedSpan = selectedTimingSpan !== undefined;
    const hasSummaryContent =
        selectedIsLlm || selectedIsEmbeddings || selectedHasTools;
    const isToolSpanSummary =
        selectedHasTools && !selectedIsLlm && !selectedIsEmbeddings;

    const headerRows = hasSelectedSpan
        ? [
              {
                  label: "Span",
                  value: selectedSpanLabel ?? "-",
              },
              {
                  label: "Duration",
                  value: selectedSpanDuration ?? "-",
              },
              {
                  label: "Offset",
                  value: formatOffsetMs(selectedOffsetMs),
              },
              ...(selectedTokenSummary !== undefined &&
              selectedTokenSummary.trim() !== ""
                  ? [
                        {
                            label: "Tokens",
                            value: selectedTokenSummary,
                        },
                    ]
                  : []),
          ]
        : [];

    return {
        timingRows,
        selection: hasSelectedSpan
            ? {
                  headerRows,
                  requestLabel: isToolSpanSummary ? undefined : "Request",
                  responseLabel: isToolSpanSummary ? undefined : "Response",
                  requestMessages: resolvedRequestMessages,
                  responseMessages: resolvedResponseMessages,
                  hasSummaryContent,
                  showToolName: selectedIsLlm || isToolSpanSummary,
                  isEmbeddings: selectedIsEmbeddings,
              }
            : undefined,
    };
};
