import {
    findHighlightMatch,
    splitHighlightText,
} from "@va/shared/lib/highlight";
import { cn } from "@va/shared/lib/utils";
import { type JSX, useMemo } from "react";

const DEFAULT_HIGHLIGHT_CLASS =
    "bg-amber-200/70 text-foreground dark:bg-amber-500/40 rounded-sm px-0.5";

const CONTEXT_BEFORE_MATCH = 8;

interface HighlightedSnippetProps {
    text: string;
    query: string;
    className?: string;
    highlightClassName?: string;
}

export const HighlightedSnippet = ({
    text,
    query,
    className,
    highlightClassName,
}: HighlightedSnippetProps): JSX.Element => {
    const displayText = useMemo(() => {
        if (query.trim() === "") {
            return text;
        }

        const match = findHighlightMatch(text, query);
        if (!match) {
            return text;
        }

        const start = Math.max(match.start - CONTEXT_BEFORE_MATCH, 0);
        const prefix = start > 0 ? "..." : "";

        return `${prefix}${text.slice(start)}`;
    }, [query, text]);

    if (query.trim() === "") {
        return <span className={className}>{text}</span>;
    }

    const parts = splitHighlightText(displayText, query);

    return (
        <span className={className}>
            {parts.map((part) =>
                part.highlight ? (
                    <mark
                        className={cn(
                            DEFAULT_HIGHLIGHT_CLASS,
                            highlightClassName,
                        )}
                        key={`${part.text}-${part.start}`}
                    >
                        {part.text}
                    </mark>
                ) : (
                    <span key={`${part.text}-${part.start}`}>{part.text}</span>
                ),
            )}
        </span>
    );
};
