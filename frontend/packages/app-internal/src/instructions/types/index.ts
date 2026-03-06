export interface PromptFile {
    filename: string;
    content: string;
}

interface PromptTemplate {
    id: string;
    filename: string;
    content: string;
}

export type ChatbotVersionScope =
    | "assistant"
    | "summary"
    | "title"
    | "title_transcript"
    | "rfi_extraction";

export interface PromptSetVersion {
    id: string;
    version_number: number;
    name: string;
    description?: string;
    is_internal: boolean;
    scope: ChatbotVersionScope;
    is_deployed: boolean;
    created_by_id: string;
    created_by_name: string;
    created_at: string;
    prompts: PromptTemplate[];
}

export interface PromptSetVersionListItem {
    id: string;
    version_number: number;
    name: string;
    description?: string;
    is_internal: boolean;
    scope: ChatbotVersionScope;
    is_deployed: boolean;
    created_by_id: string;
    created_by_name: string;
    created_at: string;
    modified_prompt_count: number;
}

export interface ActiveVersion {
    id?: string;
    version_number?: number;
    name?: string;
}

export interface PromptSetVersionCreate {
    name: string;
    description?: string;
    is_internal: boolean;
    scope: ChatbotVersionScope;
    prompts: { filename: string; content: string }[];
}

export type InstructionsTab = "editor" | "test-chat";

export type ConfirmDialogAction =
    | "delete-version"
    | "switch-version"
    | "select-default"
    | "reset-template";
