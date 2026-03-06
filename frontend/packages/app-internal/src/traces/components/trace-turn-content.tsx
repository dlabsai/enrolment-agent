import { Streamdown } from "@va/shared/components/streamdown";
import { Button } from "@va/shared/components/ui/button";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from "@va/shared/components/ui/dialog";
import { FileText } from "lucide-react";
import { type JSX, useCallback, useMemo, useState } from "react";
import { JSONTree, type ShouldExpandNodeInitially } from "react-json-tree";

import { isRecord, parseJsonRecursively } from "../lib/trace-utils";
import { jsonTreeTheme, shouldExpandJsonNode } from "../lib/trace-view-utils";
import { stringifyValue } from "./trace-turn-content-utils";

const normalizeJsonValue = (value: unknown): unknown => {
    const parsed = parseJsonRecursively(value);
    if (isRecord(parsed) || Array.isArray(parsed)) {
        return parsed;
    }
    return undefined;
};

const isJsonLikeString = (value: string): boolean => {
    const trimmed = value.trim();
    return trimmed.startsWith("{") || trimmed.startsWith("[");
};

const createJsonValueRenderer = (
    onPreview: (content: string) => void,
): ((
    displayValue: unknown,
    rawValue: unknown,
    ...keyPath: (string | number)[]
) => JSX.Element) => {
    const renderer = (
        displayValue: unknown,
        rawValue: unknown,
        ...keyPath: (string | number)[]
    ): JSX.Element => {
        const [key] = keyPath;
        const isContentKey = key === "content";
        if (
            isContentKey &&
            typeof rawValue === "string" &&
            rawValue.trim() !== "" &&
            !isJsonLikeString(rawValue)
        ) {
            return (
                <span className="inline-flex items-start gap-1">
                    <span className="whitespace-pre-wrap">
                        {String(displayValue)}
                    </span>
                    <button
                        className="text-muted-foreground hover:text-foreground"
                        onClick={(event) => {
                            event.stopPropagation();
                            onPreview(rawValue);
                        }}
                        type="button"
                    >
                        <FileText className="size-3" />
                    </button>
                </span>
            );
        }
        return <span>{String(displayValue)}</span>;
    };
    renderer.displayName = "JsonValueRenderer";
    return renderer;
};

const MarkdownContent = ({ content }: { content: string }): JSX.Element => (
    <Streamdown className="max-w-none break-words">{content}</Streamdown>
);

export const JsonValue = ({ value }: { value: unknown }): JSX.Element => {
    const [dialogContent, setDialogContent] = useState<string | undefined>();
    const [expandMode, setExpandMode] = useState<
        "auto" | "expanded" | "collapsed"
    >("auto");
    const valueRenderer = useMemo(
        () => createJsonValueRenderer(setDialogContent),
        [setDialogContent],
    );

    const shouldExpand: ShouldExpandNodeInitially = useCallback(
        (keyPath, data, level) => {
            if (expandMode === "expanded") {
                return true;
            }
            if (expandMode === "collapsed") {
                return false;
            }
            return shouldExpandJsonNode(keyPath, data, level);
        },
        [expandMode],
    );

    const treeKey = `json-${expandMode}`;

    return (
        <div className="text-sm">
            <Dialog
                onOpenChange={(open) => {
                    if (!open) {
                        setDialogContent(undefined);
                    }
                }}
                open={dialogContent !== undefined}
            >
                <div className="flex items-center justify-end pb-2">
                    <Button
                        onClick={() => {
                            setExpandMode((current) =>
                                current === "expanded"
                                    ? "collapsed"
                                    : "expanded",
                            );
                        }}
                        size="sm"
                        type="button"
                        variant="ghost"
                    >
                        {expandMode === "expanded"
                            ? "Collapse nodes"
                            : "Expand all nodes"}
                    </Button>
                </div>
                <JSONTree
                    data={value}
                    hideRoot
                    key={treeKey}
                    shouldExpandNodeInitially={shouldExpand}
                    theme={jsonTreeTheme}
                    valueRenderer={valueRenderer}
                />
                {dialogContent === undefined ? undefined : (
                    <DialogContent className="w-[88vw] max-w-[48rem] sm:max-w-[48rem]">
                        <DialogHeader>
                            <DialogTitle>Markdown preview</DialogTitle>
                        </DialogHeader>
                        <div className="max-h-[70vh] overflow-auto">
                            <MarkdownContent content={dialogContent} />
                        </div>
                    </DialogContent>
                )}
            </Dialog>
        </div>
    );
};

const safeJsonStringify = (value: unknown): string => {
    try {
        return JSON.stringify(value);
    } catch {
        return "";
    }
};

const ExpandableJson = ({
    value,
    previewHeight = 240,
}: {
    value: unknown;
    previewHeight?: number;
}): JSX.Element => {
    const serialized = useMemo(() => safeJsonStringify(value), [value]);
    const isLong = serialized.length > 800;
    const [expanded, setExpanded] = useState(!isLong);

    return (
        <div className="space-y-2">
            <div
                className={`border-muted rounded-md border px-2 py-2 ${
                    expanded ? "" : "overflow-auto"
                }`}
                style={
                    expanded ? undefined : { maxHeight: `${previewHeight}px` }
                }
            >
                <JsonValue
                    key={serialized}
                    value={value}
                />
            </div>
            {isLong ? (
                <Button
                    onClick={() => {
                        setExpanded((current) => !current);
                    }}
                    size="sm"
                    type="button"
                    variant="outline"
                >
                    {expanded ? "Show less" : "Show more"}
                </Button>
            ) : undefined}
        </div>
    );
};

const ExpandableMarkdown = ({
    content,
    previewLength = 1400,
}: {
    content: string;
    previewLength?: number;
}): JSX.Element => {
    const isLong = content.length > previewLength;
    const [expanded, setExpanded] = useState(!isLong);
    const displayContent = expanded
        ? content
        : `${content.slice(0, previewLength)}\n\n…`;

    return (
        <div className="space-y-2">
            <MarkdownContent content={displayContent} />
            {isLong ? (
                <Button
                    onClick={() => {
                        setExpanded((value) => !value);
                    }}
                    size="sm"
                    type="button"
                    variant="outline"
                >
                    {expanded ? "Show less" : "Show more"}
                </Button>
            ) : undefined}
        </div>
    );
};

const ExpandablePlainText = ({
    content,
    previewLength = 1400,
}: {
    content: string;
    previewLength?: number;
}): JSX.Element => {
    const isLong = content.length > previewLength;
    const [expanded, setExpanded] = useState(!isLong);
    const displayContent = expanded
        ? content
        : `${content.slice(0, previewLength)}\n\n…`;

    return (
        <div className="space-y-2">
            <div className="font-mono text-xs break-words whitespace-pre-wrap">
                {displayContent}
            </div>
            {isLong ? (
                <Button
                    onClick={() => {
                        setExpanded((value) => !value);
                    }}
                    size="sm"
                    type="button"
                    variant="outline"
                >
                    {expanded ? "Show less" : "Show more"}
                </Button>
            ) : undefined}
        </div>
    );
};

export const ContentValue = ({ value }: { value: unknown }): JSX.Element => {
    const jsonValue = normalizeJsonValue(value);
    if (jsonValue !== undefined) {
        return <ExpandableJson value={jsonValue} />;
    }
    if (typeof value === "string" && isJsonLikeString(value)) {
        return <ExpandablePlainText content={value} />;
    }
    return <ExpandableMarkdown content={stringifyValue(value)} />;
};
