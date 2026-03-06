import type { TraceSpan } from "../types";

interface SpanNode {
    span: TraceSpan;
    depth: number;
}

export interface TraceMessagePart {
    type: string;
    content?: string;
    raw: unknown;
}

export interface TraceMessage {
    role: string;
    content: string;
    parts?: TraceMessagePart[];
}

const normalizeString = (
    value: string | null | undefined,
): string | undefined => value ?? undefined;

export const formatTimestamp = (value: string | null | undefined): string => {
    const normalized = normalizeString(value);
    if (normalized === undefined || normalized.trim() === "") {
        return "-";
    }
    return new Date(normalized).toLocaleString("en-US", {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    });
};

export const formatDurationMs = (
    durationMs: number | null | undefined,
): string => {
    const normalized = durationMs ?? undefined;
    if (normalized === undefined || normalized <= 0) {
        return "-";
    }
    if (normalized < 1000) {
        return `${Math.round(normalized)}ms`;
    }
    return `${(normalized / 1000).toFixed(2)}s`;
};

export const formatPlatform = (value: boolean | null | undefined): string => {
    if (value === true) {
        return "Public";
    }
    if (value === false) {
        return "Internal";
    }
    return "Unknown";
};

export const isRecord = (value: unknown): value is Record<string, unknown> =>
    typeof value === "object" &&
    value instanceof Object &&
    !Array.isArray(value);

const parseJsonString = (value: string): unknown => {
    const trimmed = value.trim();
    if (
        trimmed === "" ||
        (!trimmed.startsWith("{") && !trimmed.startsWith("["))
    ) {
        return undefined;
    }
    try {
        return JSON.parse(trimmed);
    } catch {
        return undefined;
    }
};

export const parseJsonRecursively = (value: unknown): unknown => {
    if (typeof value === "string") {
        const parsed = parseJsonString(value);
        if (parsed !== undefined) {
            return parseJsonRecursively(parsed);
        }
        return value;
    }
    if (Array.isArray(value)) {
        return value.map((entry) => parseJsonRecursively(entry));
    }
    if (isRecord(value)) {
        return Object.fromEntries(
            Object.entries(value).map(([key, entry]) => [
                key,
                parseJsonRecursively(entry),
            ]),
        );
    }
    return value;
};

const toTimestamp = (value: string | null | undefined): number | undefined => {
    const normalized = normalizeString(value);
    if (normalized === undefined || normalized.trim() === "") {
        return undefined;
    }
    const parsed = Date.parse(normalized);
    return Number.isNaN(parsed) ? undefined : parsed;
};

export const getSpanStart = (span: TraceSpan): number | undefined =>
    toTimestamp(span.start_time);

export const getSpanEnd = (span: TraceSpan): number | undefined =>
    toTimestamp(span.end_time ?? span.start_time ?? undefined);

export const buildSpanTree = (spans: TraceSpan[]): SpanNode[] => {
    const rootKey = "__root__";
    const children = new Map<string, TraceSpan[]>();
    const spanIds = new Set(spans.map((span) => span.span_id));

    for (const span of spans) {
        const parentId = span.parent_span_id;
        const parent =
            typeof parentId === "string" &&
            parentId !== "" &&
            spanIds.has(parentId)
                ? parentId
                : rootKey;
        const list = children.get(parent) ?? [];
        list.push(span);
        children.set(parent, list);
    }

    for (const [key, list] of children.entries()) {
        const sorted = list.toSorted((left, right) => {
            const leftStart = getSpanStart(left) ?? 0;
            const rightStart = getSpanStart(right) ?? 0;
            return leftStart - rightStart;
        });
        children.set(key, sorted);
    }

    const ordered: SpanNode[] = [];
    const roots = children.get(rootKey) ?? [];

    const walk = (span: TraceSpan, depth: number): void => {
        ordered.push({ span, depth });
        const nested = children.get(span.span_id) ?? [];
        for (const child of nested) {
            walk(child, depth + 1);
        }
    };

    for (const root of roots) {
        walk(root, 0);
    }

    return ordered;
};

const stringifyValue = (value: unknown): string => {
    if (typeof value === "string") {
        return value;
    }
    if (typeof value === "number" || typeof value === "boolean") {
        return String(value);
    }
    return JSON.stringify(value, undefined, 2);
};

const resolveMessageContent = (value: unknown): string => {
    if (typeof value === "string") {
        return value;
    }
    if (Array.isArray(value)) {
        const hasStructured = value.some(
            (entry) => isRecord(entry) || Array.isArray(entry),
        );
        if (hasStructured) {
            return JSON.stringify(value, undefined, 2);
        }
        return value.map((part) => stringifyValue(part)).join("\n");
    }
    if (value === undefined) {
        return "";
    }
    return stringifyValue(value);
};

const parseJsonValue: (value: unknown) => unknown = (value) => {
    if (typeof value !== "string") {
        return value;
    }
    try {
        return JSON.parse(value) as unknown;
    } catch {
        return value;
    }
};

const normalizeMessageParts = (value: unknown): TraceMessagePart[] => {
    const parsed = parseJsonValue(value);
    const parts = Array.isArray(parsed) ? (parsed as unknown[]) : [];

    return parts.map((part) => {
        if (!isRecord(part)) {
            return {
                type: "unknown",
                content: resolveMessageContent(part),
                raw: part,
            };
        }
        const type = typeof part.type === "string" ? part.type : "unknown";
        const contentValue =
            part.content ??
            part.text ??
            part.output ??
            part.arguments ??
            part.result;
        const content =
            contentValue === undefined
                ? undefined
                : resolveMessageContent(contentValue);
        return {
            type,
            content,
            raw: part,
        };
    });
};

export const getStringAttribute = (
    attributes: Record<string, unknown>,
    key: string,
): string | undefined => {
    const value = attributes[key];
    return typeof value === "string" ? value : undefined;
};

const resolveFirstString = (...values: unknown[]): string | undefined =>
    values.find((value): value is string => typeof value === "string");

const normalizeToolCallEntry = (
    entry: unknown,
): { name: string; arguments: string } | undefined => {
    if (!isRecord(entry)) {
        return undefined;
    }
    const {
        name: entryName,
        tool: entryTool,
        tool_name: entryToolName,
        arguments: entryArguments,
        function: entryFunction,
        args,
        input,
    } = entry;
    const functionData = isRecord(entryFunction) ? entryFunction : undefined;
    const { name: functionName, arguments: functionArguments } =
        functionData ?? {};
    const name =
        resolveFirstString(entryName, entryToolName, entryTool, functionName) ??
        "tool";
    const argumentsValue =
        entryArguments ?? functionArguments ?? args ?? input ?? {};
    const normalizedArguments = stringifyValue(parseJsonValue(argumentsValue));
    return { name, arguments: normalizedArguments };
};

const normalizeToolResultEntry = (
    entry: unknown,
): { name: string; result: string } | undefined => {
    if (!isRecord(entry)) {
        return undefined;
    }
    const {
        name: entryName,
        tool: entryTool,
        tool_name: entryToolName,
        result,
        output,
        response,
        content,
        value,
        data,
    } = entry;

    const name =
        resolveFirstString(entryName, entryToolName, entryTool) ?? "tool";
    const resultValue =
        result ?? output ?? response ?? content ?? value ?? data;
    if (resultValue === undefined) {
        return undefined;
    }
    return {
        name,
        result: stringifyValue(parseJsonValue(resultValue)),
    };
};

const extractToolCallAttributes = (
    attributes: Record<string, unknown>,
): { name: string; arguments: string }[] => {
    const calls: { name: string; arguments: string }[] = [];
    const {
        "gen_ai.tool.call.arguments": callArguments,
        "gen_ai.tool.call": rawCallPayload,
        "gen_ai.tool.calls": rawCallsPayload,
    } = attributes;
    const callName = getStringAttribute(attributes, "gen_ai.tool.call.name");
    const toolName = getStringAttribute(attributes, "gen_ai.tool.name");
    if (
        callName !== undefined ||
        toolName !== undefined ||
        callArguments !== undefined
    ) {
        calls.push({
            name: callName ?? toolName ?? "tool",
            arguments: stringifyValue(parseJsonValue(callArguments ?? {})),
        });
    }

    const callPayload = parseJsonValue(rawCallPayload);
    if (callPayload !== undefined) {
        const callEntry = normalizeToolCallEntry(callPayload);
        if (callEntry) {
            calls.push(callEntry);
        }
    }

    const callsPayload = parseJsonValue(rawCallsPayload);
    if (Array.isArray(callsPayload)) {
        for (const entry of callsPayload) {
            const callEntry = normalizeToolCallEntry(entry);
            if (callEntry) {
                calls.push(callEntry);
            }
        }
    }

    return calls;
};

const extractToolResultAttributes = (
    attributes: Record<string, unknown>,
): { name: string; result: string }[] => {
    const results: { name: string; result: string }[] = [];
    const {
        "gen_ai.tool.result": rawResult,
        "gen_ai.tool.results": rawResults,
        "gen_ai.tool.result.value": rawResultValue,
        "gen_ai.tool.result.output": rawResultOutput,
        "gen_ai.tool.result.content": rawResultContent,
        "gen_ai.tool.output": rawToolOutput,
        "gen_ai.tool.response": rawToolResponse,
        "gen_ai.tool.call.result": rawCallResult,
        "gen_ai.tool.call.output": rawCallOutput,
        "gen_ai.tool.call.response": rawCallResponse,
        "gen_ai.tool.call.content": rawCallContent,
    } = attributes;
    const toolName =
        getStringAttribute(attributes, "gen_ai.tool.name") ??
        getStringAttribute(attributes, "gen_ai.tool.call.name");

    const directValue =
        rawResult ??
        rawResultValue ??
        rawResultOutput ??
        rawResultContent ??
        rawToolOutput ??
        rawToolResponse ??
        rawCallResult ??
        rawCallOutput ??
        rawCallResponse ??
        rawCallContent;
    if (directValue !== undefined) {
        const parsedDirect = parseJsonValue(directValue);
        if (isRecord(parsedDirect)) {
            const entry = normalizeToolResultEntry(parsedDirect);
            if (entry) {
                results.push(entry);
            }
        } else if (toolName !== undefined) {
            results.push({
                name: toolName,
                result: stringifyValue(parsedDirect),
            });
        }
    }

    const resultPayload = parseJsonValue(rawResult);
    if (Array.isArray(resultPayload)) {
        for (const entry of resultPayload) {
            const normalized = normalizeToolResultEntry(entry);
            if (normalized) {
                results.push(normalized);
            }
        }
    }

    const resultsPayload = parseJsonValue(rawResults);
    if (Array.isArray(resultsPayload)) {
        for (const entry of resultsPayload) {
            const normalized = normalizeToolResultEntry(entry);
            if (normalized) {
                results.push(normalized);
            }
        }
    } else if (isRecord(resultsPayload)) {
        const normalized = normalizeToolResultEntry(resultsPayload);
        if (normalized) {
            results.push(normalized);
        }
    }

    return results;
};

const normalizeMessages = (value: unknown): unknown[] => {
    const parsed = parseJsonValue(value);
    if (Array.isArray(parsed)) {
        return parsed;
    }
    if (isRecord(parsed)) {
        if (Array.isArray(parsed.messages)) {
            return parsed.messages;
        }
        if (parsed.message !== undefined) {
            return [parsed.message];
        }
    }
    return [];
};

const normalizeToolCalls = (value: unknown): unknown[] => {
    const parsed = parseJsonValue(value);
    if (Array.isArray(parsed)) {
        const fromMessages: unknown[] = [];
        for (const item of parsed) {
            if (isRecord(item)) {
                const { tool_calls: toolCalls, parts, message } = item;
                if (Array.isArray(toolCalls)) {
                    for (const call of toolCalls) {
                        fromMessages.push(call);
                    }
                }
                if (Array.isArray(parts)) {
                    for (const part of parts) {
                        if (isRecord(part)) {
                            const { type } = part;
                            if (type === "tool_call") {
                                fromMessages.push(part);
                            }
                        }
                    }
                }
                if (isRecord(message) && Array.isArray(message.tool_calls)) {
                    for (const call of message.tool_calls) {
                        fromMessages.push(call);
                    }
                }
                if (isRecord(message) && Array.isArray(message.parts)) {
                    for (const part of message.parts) {
                        if (isRecord(part)) {
                            const { type } = part;
                            if (type === "tool_call") {
                                fromMessages.push(part);
                            }
                        }
                    }
                }
            }
        }
        return fromMessages.length > 0 ? fromMessages : parsed;
    }
    if (isRecord(parsed)) {
        const { tool_calls: toolCalls, message, parts } = parsed;
        if (Array.isArray(toolCalls)) {
            return toolCalls;
        }
        if (isRecord(message) && Array.isArray(message.tool_calls)) {
            return message.tool_calls;
        }
        if (Array.isArray(parts)) {
            return parts.filter((part) => {
                if (!isRecord(part)) {
                    return false;
                }
                const { type } = part;
                return type === "tool_call";
            });
        }
    }
    return [];
};

const extractMessages = (
    attributes: Record<string, unknown>,
    key: string,
): TraceMessage[] => {
    const raw = attributes[key];
    const items = normalizeMessages(raw);
    if (items.length === 0) {
        return [];
    }

    const messages: TraceMessage[] = [];
    for (const item of items) {
        if (isRecord(item)) {
            const {
                role: itemRole,
                content,
                text,
                message,
                data,
                parts,
            } = item;
            const role = typeof itemRole === "string" ? itemRole : "message";
            const normalizedParts =
                parts === undefined ? [] : normalizeMessageParts(parts);
            const resolvedContent = resolveMessageContent(
                content ?? text ?? message ?? data ?? parts,
            );
            messages.push({
                role,
                content: resolvedContent,
                parts: normalizedParts.length > 0 ? normalizedParts : undefined,
            });
        }
    }
    return messages;
};

const extractToolCalls = (
    attributes: Record<string, unknown>,
    key: string,
): { name: string; arguments: string }[] => {
    const raw = attributes[key];
    const items = normalizeToolCalls(raw);
    if (items.length === 0) {
        return [];
    }

    const calls: { name: string; arguments: string }[] = [];
    for (const item of items) {
        const callEntry = normalizeToolCallEntry(item);
        if (callEntry) {
            calls.push(callEntry);
        }
    }
    return calls;
};

const firstNonEmpty = <T>(values: T[][]): T[] => {
    for (const value of values) {
        if (value.length > 0) {
            return value;
        }
    }
    return [];
};

export const extractRequestMessages = (
    attributes: Record<string, unknown>,
): { role: string; content: string }[] =>
    firstNonEmpty([
        extractMessages(attributes, "gen_ai.request.messages"),
        extractMessages(attributes, "gen_ai.input.messages"),
        extractMessages(attributes, "request_data"),
    ]);

export const extractResponseMessages = (
    attributes: Record<string, unknown>,
): { role: string; content: string }[] =>
    firstNonEmpty([
        extractMessages(attributes, "gen_ai.response.messages"),
        extractMessages(attributes, "gen_ai.output.messages"),
        extractMessages(attributes, "response_data"),
    ]);

export const extractResponseToolCalls = (
    attributes: Record<string, unknown>,
): { name: string; arguments: string }[] =>
    firstNonEmpty([
        extractToolCalls(attributes, "gen_ai.response.tool_calls"),
        extractToolCalls(attributes, "response_data"),
        extractToolCallAttributes(attributes),
    ]);

export const extractToolResults = (
    attributes: Record<string, unknown>,
): { name: string; result: string }[] =>
    extractToolResultAttributes(attributes);

export const extractRequestTools = (
    attributes: Record<string, unknown>,
): { name: string; arguments: string }[] =>
    firstNonEmpty([
        extractToolCalls(attributes, "gen_ai.request.tools"),
        extractToolCalls(attributes, "request_data"),
        extractToolCallAttributes(attributes),
    ]);
