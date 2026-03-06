import type {
    LoadingActivityLogEntry,
    LoadingToolState,
} from "@va/shared/types";

import {
    extractResponseToolCalls,
    extractToolResults,
    getSpanEnd,
    getSpanStart,
    getStringAttribute,
    isRecord,
    parseJsonRecursively,
} from "../../traces/lib/trace-utils";
import type { TraceDetail, TraceSpan } from "../../traces/types";

const AGENT_LABELS: Record<string, string> = {
    search: "Search agent",
    chatbot: "Chatbot agent",
    guardrails: "Guardrails agent",
};

const ALLOWED_AGENT_NAMES = new Set(Object.keys(AGENT_LABELS));

const normalizeAgentLabel = (agentName: string): string =>
    AGENT_LABELS[agentName] ?? agentName.replaceAll("_", " ");

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
        return ALLOWED_AGENT_NAMES.has(direct) ? direct : undefined;
    }

    let parentId: string | undefined = span.parent_span_id ?? undefined;
    const visited = new Set<string>();
    while (parentId !== undefined && parentId.trim() !== "") {
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
            return ALLOWED_AGENT_NAMES.has(agentName) ? agentName : undefined;
        }
        parentId = parent.parent_span_id ?? undefined;
    }
    return undefined;
};

const extractThinkingFromMessages = (value: unknown): string[] => {
    const parsed = parseJsonRecursively(value);
    if (!Array.isArray(parsed)) {
        return [];
    }
    const results: string[] = [];
    for (const message of parsed) {
        if (isRecord(message)) {
            const role =
                typeof message.role === "string" ? message.role : undefined;
            const roleMatches = role === undefined || role === "assistant";
            if (roleMatches && Array.isArray(message.parts)) {
                for (const part of message.parts) {
                    if (isRecord(part) && part.type === "thinking") {
                        const { content } = part;
                        if (
                            typeof content === "string" &&
                            content.trim() !== ""
                        ) {
                            results.push(content);
                        }
                    }
                }
            }
        }
    }
    return results;
};

const resolveReasoningParts = (
    attributes: Record<string, unknown>,
): string[] => {
    const parts: string[] = [];
    const candidates = [
        "gen_ai.response.reasoning",
        "gen_ai.response.reasoning_summary",
        "gen_ai.response.reasoning_text",
        "openai.response.reasoning",
        "openai.response.reasoning_summary",
        "openai.response.reasoning_text",
        "response.reasoning",
        "response.reasoning_summary",
    ];

    for (const key of candidates) {
        const value = attributes[key];
        if (typeof value === "string" && value.trim() !== "") {
            parts.push(value);
        }
    }

    const thinkingMessages = [
        "gen_ai.output.messages",
        "gen_ai.response.messages",
    ];
    for (const key of thinkingMessages) {
        const raw = attributes[key];
        if (raw !== undefined) {
            const thinkingParts = extractThinkingFromMessages(raw);
            for (const thinking of thinkingParts) {
                if (thinking.trim() !== "") {
                    parts.push(thinking);
                }
            }
        }
    }

    return parts;
};

const resolveDurationMs = (span: TraceSpan): number | undefined => {
    if (typeof span.duration_ms === "number") {
        return span.duration_ms;
    }
    const start = getSpanStart(span);
    const end = getSpanEnd(span);
    if (start === undefined || end === undefined) {
        return undefined;
    }
    return end - start;
};

const resolveToolState = (
    isError: boolean,
    hasOutput: boolean,
): LoadingToolState => {
    if (isError) {
        return "output-error";
    }
    if (hasOutput) {
        return "output-available";
    }
    return "input-available";
};

export const buildActivityLogFromTrace = (
    detail: TraceDetail,
): LoadingActivityLogEntry[] => {
    const { spans } = detail;
    if (spans.length === 0) {
        return [];
    }

    const spanLookup = buildSpanLookup(spans);
    const ordered = spans.toSorted((left, right) => {
        const leftStart = getSpanStart(left) ?? 0;
        const rightStart = getSpanStart(right) ?? 0;
        return leftStart - rightStart;
    });

    const entries: LoadingActivityLogEntry[] = [];
    const agentCounts = new Map<string, number>();
    const agentIdMap = new Map<string, string>();
    const pendingToolEntriesById = new Map<string, LoadingActivityLogEntry>();
    const pendingToolEntriesByName = new Map<
        string,
        LoadingActivityLogEntry[]
    >();
    let sequence = 0;

    for (const span of ordered) {
        const attributes = span.attributes ?? {};
        const directAgent = getStringAttribute(attributes, "gen_ai.agent.name");
        if (
            directAgent !== undefined &&
            directAgent.trim() !== "" &&
            ALLOWED_AGENT_NAMES.has(directAgent)
        ) {
            const count = agentCounts.get(directAgent) ?? 0;
            agentCounts.set(directAgent, count + 1);
            const suffix = count === 0 ? "" : `:${count + 1}`;
            const agentId = `agent:${directAgent}${suffix}`;
            agentIdMap.set(directAgent, agentId);

            entries.push({
                id: agentId,
                sequence,
                label: normalizeAgentLabel(directAgent),
                status: "complete",
                kind: "agent",
                startedAtMs: getSpanStart(span),
                durationMs: resolveDurationMs(span),
            });
            sequence += 1;
        }

        const agentName = resolveAgentName(span, spanLookup);
        const parentId =
            agentName === undefined
                ? undefined
                : (agentIdMap.get(agentName) ?? undefined);

        const reasoningParts = resolveReasoningParts(attributes);
        if (agentName !== undefined && reasoningParts.length > 0) {
            for (const [index, reasoning] of reasoningParts.entries()) {
                if (reasoning.trim() !== "") {
                    entries.push({
                        id: `thinking:${span.span_id}:${index}`,
                        sequence,
                        label: `${normalizeAgentLabel(agentName)} reasoning`,
                        status: "complete",
                        kind: "thinking",
                        parentId,
                        thinkingContent: reasoning,
                    });
                    sequence += 1;
                }
            }
        }

        const toolCalls = extractResponseToolCalls(attributes);
        const toolResults = extractToolResults(attributes);
        const spanToolCallId = getStringAttribute(
            attributes,
            "gen_ai.tool.call.id",
        );
        const spanToolName =
            getStringAttribute(attributes, "gen_ai.tool.name") ??
            getStringAttribute(attributes, "gen_ai.tool.call.name");
        const spanToolArgs = attributes["gen_ai.tool.call.arguments"];
        const fallbackToolCalls =
            toolCalls.length > 0
                ? toolCalls.map((call) =>
                      spanToolName !== undefined && call.name === "tool"
                          ? { ...call, name: spanToolName }
                          : call,
                  )
                : spanToolName !== undefined && spanToolArgs !== undefined
                  ? [
                        {
                            name: spanToolName,
                            arguments:
                                typeof spanToolArgs === "string"
                                    ? spanToolArgs
                                    : JSON.stringify(spanToolArgs),
                        },
                    ]
                  : [];

        if (fallbackToolCalls.length > 0 || toolResults.length > 0) {
            const resultsByName = new Map<string, string[]>();
            for (const result of toolResults) {
                const list = resultsByName.get(result.name) ?? [];
                list.push(result.result);
                resultsByName.set(result.name, list);
            }

            if (
                spanToolName !== undefined &&
                resultsByName.has("tool") &&
                !resultsByName.has(spanToolName)
            ) {
                const unnamed = resultsByName.get("tool") ?? [];
                resultsByName.delete("tool");
                resultsByName.set(spanToolName, unnamed);
            }

            const spanIsError = span.status_code === "ERROR";
            const popPendingByName = (
                name: string,
            ): LoadingActivityLogEntry | undefined => {
                const list = pendingToolEntriesByName.get(name);
                if (list === undefined || list.length === 0) {
                    return undefined;
                }
                const entry = list.shift();
                if (list.length === 0) {
                    pendingToolEntriesByName.delete(name);
                }
                return entry;
            };

            const registerPendingEntry = (
                name: string,
                entry: LoadingActivityLogEntry,
                callId?: string,
            ): void => {
                if (callId !== undefined && callId.trim() !== "") {
                    pendingToolEntriesById.set(callId, entry);
                    return;
                }
                const list = pendingToolEntriesByName.get(name) ?? [];
                list.push(entry);
                pendingToolEntriesByName.set(name, list);
            };

            for (const [index, call] of fallbackToolCalls.entries()) {
                const results = resultsByName.get(call.name);
                const result = results?.shift();
                const hasOutput = result !== undefined;
                const toolOutput =
                    result === undefined
                        ? undefined
                        : parseJsonRecursively(result);
                const toolInput = parseJsonRecursively(call.arguments);
                const toolState = resolveToolState(spanIsError, hasOutput);
                const callId =
                    spanToolCallId !== undefined &&
                    spanToolCallId.trim() !== "" &&
                    fallbackToolCalls.length === 1
                        ? spanToolCallId
                        : undefined;
                const existing =
                    callId === undefined
                        ? undefined
                        : pendingToolEntriesById.get(callId);

                if (existing) {
                    existing.toolInput = toolInput;
                    if (toolOutput !== undefined) {
                        existing.toolOutput = toolOutput;
                        existing.toolState = resolveToolState(
                            spanIsError,
                            true,
                        );
                        existing.status = spanIsError ? "error" : "complete";
                        existing.toolErrorText = spanIsError
                            ? (span.status_message ?? "Tool error")
                            : undefined;
                        if (callId !== undefined) {
                            pendingToolEntriesById.delete(callId);
                        }
                    }
                } else {
                    const entry: LoadingActivityLogEntry = {
                        id: `tool:${span.span_id}:${index}`,
                        sequence,
                        label: `Using tool: ${call.name}`,
                        status: spanIsError ? "error" : "complete",
                        kind: "tool",
                        parentId,
                        toolName: call.name,
                        toolInput,
                        toolOutput,
                        toolErrorText: spanIsError
                            ? (span.status_message ?? "Tool error")
                            : undefined,
                        toolState,
                    };
                    entries.push(entry);
                    sequence += 1;

                    if (!hasOutput) {
                        registerPendingEntry(call.name, entry, callId);
                    }
                }
            }

            let resultIndex = fallbackToolCalls.length;
            for (const [name, values] of resultsByName.entries()) {
                for (const result of values) {
                    const toolOutput = parseJsonRecursively(result);
                    const entryById =
                        spanToolCallId === undefined
                            ? undefined
                            : pendingToolEntriesById.get(spanToolCallId);
                    const pendingEntry = entryById ?? popPendingByName(name);
                    if (pendingEntry) {
                        pendingEntry.toolOutput = toolOutput;
                        pendingEntry.toolState = resolveToolState(
                            spanIsError,
                            true,
                        );
                        pendingEntry.status = spanIsError
                            ? "error"
                            : "complete";
                        pendingEntry.toolErrorText = spanIsError
                            ? (span.status_message ?? "Tool error")
                            : undefined;
                        if (entryById && spanToolCallId !== undefined) {
                            pendingToolEntriesById.delete(spanToolCallId);
                        }
                    } else {
                        entries.push({
                            id: `tool:${span.span_id}:${resultIndex}`,
                            sequence,
                            label: `Using tool: ${name}`,
                            status: spanIsError ? "error" : "complete",
                            kind: "tool",
                            parentId,
                            toolName: name,
                            toolOutput,
                            toolErrorText: spanIsError
                                ? (span.status_message ?? "Tool error")
                                : undefined,
                            toolState: resolveToolState(spanIsError, true),
                        });
                        sequence += 1;
                        resultIndex += 1;
                    }
                }
            }
        }
    }

    return entries;
};
