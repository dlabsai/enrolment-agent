import type {
    LoadingActivityItem,
    LoadingActivityLogEntry,
} from "@va/shared/types";

export interface Message {
    id: string;
    role: "user" | "assistant";
    content: string;
    createdAt: number;
    parentId?: string;
    isError?: boolean;
}

export type Rating = "thumbsUp" | "thumbsDown";

export interface MessageFeedback {
    id: string;
    rating: Rating;
    text?: string;
    user_id: string;
    user_name: string;
    is_current_user: boolean;
    created_at: string;
    updated_at: string;
}

export interface Chat {
    id: string;
    title?: string;
    summary?: string;
    lastMessagePreview?: string;
    updatedAt: number;
    isPublic: boolean;
    userName?: string;
    userEmail?: string;
    messages: Message[];
    isLoading: boolean;
    hasUnread: boolean;
    loadingActivity?: LoadingActivityItem[];
    loadingActivityLog?: LoadingActivityLogEntry[];
    parentMessageId?: string;
}

export interface ChatListItem {
    id: string;
    title?: string;
    summary?: string;
    last_message_preview?: string;
    message_count: number;
    created_at: string;
    updated_at: string;
    is_public: boolean;
    user_name?: string;
    user_email?: string;
}

export interface ChatDetailResponse {
    id: string;
    title?: string;
    summary?: string;
    messages: {
        id: string;
        role: "user" | "assistant";
        content: string;
        parent_id?: string;
        created_at: string;
        feedback?: MessageFeedback[];
    }[];
    created_at: string;
    updated_at: string;
}

interface ConversationTreeMessageResponse {
    id: string;
    role: "user" | "assistant";
    content: string;
    created_at: string;
    parent_id: string | null;
    guardrails_blocked?: boolean;
    feedback?: MessageFeedback[];
}

interface ConversationTreeNodeResponse {
    message: ConversationTreeMessageResponse;
    message_tree_nodes: ConversationTreeNodeResponse[];
}

export interface ConversationTreeResponse {
    message_tree_nodes: Record<string, ConversationTreeNodeResponse>;
    current_branch_path: string[];
    subtree_active_paths: Record<string, string[]>;
}

export interface ConversationDetailTreeResponse {
    id: string;
    title?: string;
    user: boolean;
    conversation_tree: ConversationTreeResponse;
    created_at: string;
    updated_at: string;
}

export interface ChatSearchResult {
    id: string;
    title?: string;
    snippet: string;
    updatedAt: string;
}

export interface ModelOverrides {
    chatbotModel?: string;
    searchModel?: string;
    guardrailModel?: string;
    chatbotReasoningEffort?: "none" | "low" | "medium" | "high" | "xhigh";
    searchReasoningEffort?: "none" | "low" | "medium" | "high" | "xhigh";
    guardrailReasoningEffort?: "none" | "low" | "medium" | "high" | "xhigh";
}
