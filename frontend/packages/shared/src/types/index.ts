export interface ChatMessage {
    id: string;
    role: "user" | "assistant";
    content: string;
    timestamp: number;
    isLoading?: boolean;
}

export type LoadingActivityStatus = "in_progress" | "complete" | "error";

export type LoadingActivityKind = "agent" | "tool" | "thinking";

export type LoadingToolState =
    | "input-streaming"
    | "input-available"
    | "approval-requested"
    | "approval-responded"
    | "output-available"
    | "output-error"
    | "output-denied";

export interface LoadingActivityItem {
    id: string;
    label: string;
    status: LoadingActivityStatus;
    parentId?: string;
    kind?: LoadingActivityKind;
    toolState?: LoadingToolState;
    toolName?: string;
    toolInput?: unknown;
    toolOutput?: unknown;
    toolErrorText?: string;
    thinkingContent?: string;
}

export interface LoadingActivityLogEntry {
    id: string;
    sequence: number;
    label: string;
    status: LoadingActivityStatus;
    parentId?: string;
    kind?: LoadingActivityKind;
    toolState?: LoadingToolState;
    toolName?: string;
    toolInput?: unknown;
    toolOutput?: unknown;
    toolErrorText?: string;
    thinkingContent?: string;
    startedAtMs?: number;
    durationMs?: number;
}

export interface LoadingIndicatorProps {
    isVisible: boolean;
    onTextShow?: () => void;
    messages?: string[];
    activityItems?: LoadingActivityItem[];
    activityLog?: LoadingActivityLogEntry[];
    variant?: "default" | "shimmer" | "ai-elements";
    showHeader?: boolean;
    forceOpenReasoning?: boolean;
    showEmptyState?: boolean;
}
