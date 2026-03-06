import type { ChatbotVersionScope, PromptFile } from "../types";

export type PromptPlatform = "internal" | "public";

export interface AdminSection {
    id: string;
    label: string;
    platform: PromptPlatform;
    templates: string[];
}

const ASSISTANT_TEMPLATES = [
    "search_agent",
    "chatbot_agent",
    "guardrails_agent",
] as const;

const ASSISTANT_TEMPLATE_SET = new Set<string>(ASSISTANT_TEMPLATES);

const HELPERS = [
    { key: "summary", label: "Summary", template: "summary_agent" },
    { key: "title", label: "Title", template: "title_agent" },
    {
        key: "title-transcript",
        label: "Title Transcript",
        template: "title_agent_transcript",
    },
    {
        key: "rfi-extraction",
        label: "RFI Extraction",
        template: "rfi_extraction_agent",
    },
] as const;

const SECTION_SCOPE_MAP: Record<string, ChatbotVersionScope> = {
    assistant: "assistant",
    summary: "summary",
    title: "title",
    "title-transcript": "title_transcript",
    "rfi-extraction": "rfi_extraction",
};

const SCOPE_SECTION_KEY_MAP: Record<ChatbotVersionScope, string> = {
    assistant: "assistant",
    summary: "summary",
    title: "title",
    title_transcript: "title-transcript",
    rfi_extraction: "rfi-extraction",
};

const HELPER_TEMPLATE_BY_SCOPE: Record<
    ChatbotVersionScope,
    string | undefined
> = {
    assistant: undefined,
    summary: "summary_agent",
    title: "title_agent",
    title_transcript: "title_agent_transcript",
    rfi_extraction: "rfi_extraction_agent",
};

const TEMPLATE_LABELS: Record<string, string> = {
    search_agent: "Search",
    chatbot_agent: "Chatbot",
    guardrails_agent: "Guardrails",
    summary_agent: "Summary",
    rfi_extraction_agent: "RFI Extraction",
    title_agent: "Title",
    title_agent_transcript: "Title Transcript",
};

const DEFAULT_TEMPLATE_PRIORITY = [
    "search_agent_internal.j2",
    "chatbot_agent_internal.j2",
    "guardrails_agent_internal.j2",
    "search_agent.j2",
    "chatbot_agent.j2",
    "guardrails_agent.j2",
    "summary_agent_internal.j2",
    "summary_agent.j2",
    "title_agent_internal.j2",
    "title_agent.j2",
    "title_agent_transcript_internal.j2",
    "title_agent_transcript.j2",
    "rfi_extraction_agent.j2",
];

const getFilenameForBase = (base: string, platform: PromptPlatform): string =>
    platform === "internal" ? `${base}_internal.j2` : `${base}.j2`;

export const getPlatformForFilename = (filename: string): PromptPlatform =>
    filename.includes("_internal") ? "internal" : "public";

export const getTemplateLabel = (filename: string): string => {
    const baseName = filename
        .replace(/_internal\.j2$/u, "")
        .replace(/\.j2$/u, "");
    return TEMPLATE_LABELS[baseName] ?? baseName;
};

const formatScopeLabel = (platform: PromptPlatform): string =>
    platform === "internal" ? "Internal" : "Public";

const createSectionId = (key: string, platform: PromptPlatform): string =>
    `${key}-${platform}`;

export const getScopeForSectionId = (
    sectionId?: string,
): ChatbotVersionScope | undefined => {
    if (sectionId === undefined || sectionId === "") {
        return undefined;
    }
    const key = sectionId.replace(/-internal$/u, "").replace(/-public$/u, "");
    return SECTION_SCOPE_MAP[key];
};

export const getSectionIdForScope = (
    scope: ChatbotVersionScope,
    platform: PromptPlatform,
): string => createSectionId(SCOPE_SECTION_KEY_MAP[scope], platform);

export const getPlatformForSectionId = (
    sectionId?: string,
): PromptPlatform | undefined => {
    if (sectionId === undefined || sectionId === "") {
        return undefined;
    }
    if (sectionId.endsWith("-internal")) {
        return "internal";
    }
    if (sectionId.endsWith("-public")) {
        return "public";
    }
    return undefined;
};

export const getTemplateFilenamesForScope = (
    scope: ChatbotVersionScope,
    platform: PromptPlatform,
): string[] => {
    if (scope === "assistant") {
        return ASSISTANT_TEMPLATES.map((base) =>
            getFilenameForBase(base, platform),
        );
    }

    const helperTemplate = HELPER_TEMPLATE_BY_SCOPE[scope];
    if (helperTemplate === undefined) {
        return [];
    }
    return [getFilenameForBase(helperTemplate, platform)];
};

export const buildSections = (diskTemplates: PromptFile[]): AdminSection[] => {
    const templateSet = new Set(
        diskTemplates.map((template) => template.filename),
    );
    const sections: AdminSection[] = [];

    const addAssistantSection = (platform: PromptPlatform): void => {
        const templates = ASSISTANT_TEMPLATES.map((base) =>
            getFilenameForBase(base, platform),
        ).filter((filename) => templateSet.has(filename));

        if (templates.length === 0) {
            return;
        }

        sections.push({
            id: createSectionId("assistant", platform),
            label: `Assistant (${formatScopeLabel(platform)})`,
            platform,
            templates,
        });
    };

    const addHelperSections = (platform: PromptPlatform): void => {
        for (const helper of HELPERS) {
            const filename = getFilenameForBase(helper.template, platform);
            if (templateSet.has(filename)) {
                sections.push({
                    id: createSectionId(helper.key, platform),
                    label: `${helper.label} (${formatScopeLabel(platform)})`,
                    platform,
                    templates: [filename],
                });
            }
        }
    };

    addAssistantSection("internal");
    addAssistantSection("public");
    addHelperSections("internal");
    addHelperSections("public");

    return sections;
};

export const isAssistantSectionId = (sectionId?: string): boolean =>
    sectionId?.startsWith("assistant-") ?? false;

export const getSectionIdForTemplate = (
    filename: string,
): string | undefined => {
    const platform = getPlatformForFilename(filename);
    const baseName = filename
        .replace(/_internal\.j2$/u, "")
        .replace(/\.j2$/u, "");

    if (ASSISTANT_TEMPLATE_SET.has(baseName)) {
        return createSectionId("assistant", platform);
    }

    const helper = HELPERS.find((item) => item.template === baseName);
    if (helper) {
        return createSectionId(helper.key, platform);
    }

    return undefined;
};

export const getDefaultTemplateFilename = (
    diskTemplates: PromptFile[],
): string | undefined => {
    const templateSet = new Set(
        diskTemplates.map((template) => template.filename),
    );

    return DEFAULT_TEMPLATE_PRIORITY.find((filename) =>
        templateSet.has(filename),
    );
};
