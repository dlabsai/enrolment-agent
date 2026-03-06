import {
    isRecord,
    type TraceMessage,
    type TraceMessagePart,
} from "../lib/trace-utils";

export const getStringField = (
    value: Record<string, unknown> | undefined,
    key: string,
): string | undefined => {
    if (!value) {
        return undefined;
    }
    const entry = value[key];
    return typeof entry === "string" ? entry : undefined;
};

export const buildMessagePartKey = (part: TraceMessagePart): string => {
    const raw = isRecord(part.raw) ? part.raw : undefined;
    const rawId = getStringField(raw, "id");
    const rawName = getStringField(raw, "name");
    const content = part.content ?? "";
    return `${part.type}-${rawId ?? rawName ?? content}`;
};

export const buildMessageKey = (message: TraceMessage): string => {
    const partsCount = message.parts === undefined ? 0 : message.parts.length;
    return `${message.role}-${message.content}-${partsCount}`;
};
