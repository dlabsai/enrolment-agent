import type { Theme } from "react-base16-styling";
import type { ShouldExpandNodeInitially } from "react-json-tree";

import type { TraceSpan } from "../types";
import { formatDurationMs, getSpanStart } from "./trace-utils";

const JSON_TREE_EXPAND_DEPTH = 2;
// Measured Structured first render after reload (Raw → Structured tab switch).
//
// | JSON_TREE_EXPAND_DEPTH | Samples (ms)        | Avg (ms) |
// | ---------------------- | ------------------- | -------- |
// | 1                      | 166.6, 173.0, 161.7 | 167.1    |
// | 2                      | 308.8, 291.7, 277.5 | 292.7    |
// | 3                      | 629.6, 640.2, 549.1 | 606.3    |
//
// Impact: depth 1 → 2 adds ~125ms; 2 → 3 adds ~314ms.

export interface SpanTreeNode {
    span: TraceSpan;
    children: SpanTreeNode[];
}

export const buildSpanHierarchy = (spans: TraceSpan[]): SpanTreeNode[] => {
    const nodes = new Map<string, SpanTreeNode>();
    for (const span of spans) {
        nodes.set(span.span_id, { span, children: [] });
    }

    const roots: SpanTreeNode[] = [];
    for (const span of spans) {
        const node = nodes.get(span.span_id);
        if (node) {
            const parentId = span.parent_span_id;
            const parent =
                typeof parentId === "string" && parentId !== ""
                    ? nodes.get(parentId)
                    : undefined;
            if (parent) {
                parent.children.push(node);
            } else {
                roots.push(node);
            }
        }
    }

    const sortNodes = (items: SpanTreeNode[]): void => {
        items.sort((left, right) => {
            const leftStart = getSpanStart(left.span) ?? 0;
            const rightStart = getSpanStart(right.span) ?? 0;
            return leftStart - rightStart;
        });
        for (const item of items) {
            sortNodes(item.children);
        }
    };

    sortNodes(roots);
    return roots;
};

export const formatSpanDuration = (span: TraceSpan): string =>
    formatDurationMs(span.duration_ms);

export const shouldExpandJsonNode: ShouldExpandNodeInitially = (
    _keyPath,
    _data,
    level,
): boolean => level < JSON_TREE_EXPAND_DEPTH;

export const jsonTreeTheme: Theme = {
    scheme: "shadcn",
    author: "va",
    base00: "var(--background)",
    base01: "var(--border)",
    base02: "var(--muted)",
    base03: "var(--muted-foreground)",
    base04: "var(--muted-foreground)",
    base05: "var(--foreground)",
    base06: "var(--foreground)",
    base07: "var(--foreground)",
    base08: "var(--destructive)",
    base09: "var(--chart-5)",
    base0A: "var(--chart-3)",
    base0B: "var(--chart-2)",
    base0C: "var(--chart-4)",
    base0D: "var(--primary)",
    base0E: "var(--chart-1)",
    base0F: "var(--chart-5)",
};
