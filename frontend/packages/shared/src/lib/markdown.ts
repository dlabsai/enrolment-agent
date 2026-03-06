export const markdownToPlainText = (content: string): string => {
    if (content === "") {
        return "";
    }

    let text = content.replaceAll(/```[\s\S]*?```/gu, "");
    text = text.replaceAll(/`(?<code>[^`]+)`/gu, "$<code>");
    text = text.replaceAll(/\[(?<linkText>[^\]]+)\]\([^)]+\)/gu, "$<linkText>");
    text = text.replaceAll(/!\[(?<altText>[^\]]*)\]\([^)]+\)/gu, "$<altText>");
    text = text.replaceAll(
        /(?<marker>\*\*|__)(?<content>.*?)\k<marker>/gu,
        "$<content>",
    );
    text = text.replaceAll(
        /(?<marker>\*|_)(?<content>.*?)\k<marker>/gu,
        "$<content>",
    );
    text = text.replaceAll(/^#{1,6}\s+/gmu, "");
    text = text.replaceAll(/^>\s+/gmu, "");
    text = text.replaceAll(/^[*+-]\s+/gmu, "");
    text = text.replaceAll(/^\d+\.\s+/gmu, "");
    text = text.replaceAll(/^(?:\*{3,}|-{3,}|_{3,})$/gmu, "");
    text = text.replaceAll(/\n{3,}/gu, "\n\n");
    text = text.trim();

    return text;
};
