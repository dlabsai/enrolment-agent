const escapeRegExp = (value: string): string =>
    value.replaceAll(/[$()*+.?[\\\]^{|}]/gu, String.raw`\$&`);

const getHighlightRegex = (query: string): RegExp | undefined => {
    const terms = query.trim().split(/\s+/u).filter(Boolean);
    if (terms.length === 0) {
        return undefined;
    }

    const escaped = terms.map((term) => escapeRegExp(term)).join("|");
    return new RegExp(`(${escaped})`, "giu");
};

interface HighlightPart {
    text: string;
    highlight: boolean;
    start: number;
}

export const splitHighlightText = (
    text: string,
    query: string,
): HighlightPart[] => {
    const regex = getHighlightRegex(query);
    if (!regex) {
        return [{ text, highlight: false, start: 0 }];
    }

    const results: HighlightPart[] = [];
    let lastIndex = 0;
    let match: RegExpExecArray | null = regex.exec(text);
    while (match !== null) {
        if (match.index > lastIndex) {
            results.push({
                text: text.slice(lastIndex, match.index),
                highlight: false,
                start: lastIndex,
            });
        }
        const [matchText] = match;
        results.push({
            text: matchText,
            highlight: true,
            start: match.index,
        });
        lastIndex = match.index + matchText.length;
        match = regex.exec(text);
    }
    if (lastIndex < text.length) {
        results.push({
            text: text.slice(lastIndex),
            highlight: false,
            start: lastIndex,
        });
    }
    return results.filter((part) => part.text !== "");
};

export const findHighlightMatch = (
    text: string,
    query: string,
): { start: number; end: number } | undefined => {
    const regex = getHighlightRegex(query);
    if (!regex) {
        return undefined;
    }

    const match = regex.exec(text);
    if (!match) {
        return undefined;
    }

    return {
        start: match.index,
        end: match.index + match[0].length,
    };
};
