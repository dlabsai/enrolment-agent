import { API_URL } from "@va/shared/config";
import { isRecord } from "@va/shared/lib/type-guards";

import type { AuthenticatedApi } from "../../auth/hooks/use-authenticated-api";
import type {
    ChatDetailResponse,
    ChatListItem,
    ChatSearchResult,
    ConversationDetailTreeResponse,
    MessageFeedback,
    ModelOverrides,
    Rating,
} from "../types";

const CHATS_BASE = "/conversations";

export const fetchChats = async (
    api: AuthenticatedApi,
): Promise<ChatListItem[]> => api.get<ChatListItem[]>(CHATS_BASE);

export const fetchChatDetail = async (
    api: AuthenticatedApi,
    chatId: string,
): Promise<ChatDetailResponse> =>
    api.get<ChatDetailResponse>(`${CHATS_BASE}/${chatId}`);

export const deleteChat = async (
    api: AuthenticatedApi,
    chatId: string,
): Promise<void> => {
    await api.delete(`${CHATS_BASE}/${chatId}`);
};

export const renameChatTitle = async (
    api: AuthenticatedApi,
    chatId: string,
    title: string,
): Promise<string> => {
    const response = await api.put<{ title: string }>(
        `${CHATS_BASE}/${chatId}/title`,
        {
            title,
        },
    );
    return response.title;
};

export const regenerateChatTitle = async (
    api: AuthenticatedApi,
    chatId: string,
): Promise<string> => {
    const response = await api.post<{ title: string }>(
        `${CHATS_BASE}/${chatId}/title/regenerate`,
        {},
    );
    return response.title;
};

interface ChatSearchResultResponse {
    id: string;
    title?: string | null;
    snippet: string;
    updated_at: string;
}

export const searchChats = async (
    api: AuthenticatedApi,
    params: {
        search: string;
        limit?: number;
        offset?: number;
    },
): Promise<ChatSearchResult[]> => {
    const query = new URLSearchParams();
    query.set("search", params.search.trim());
    if (params.offset !== undefined) {
        query.set("offset", String(params.offset));
    }
    if (params.limit !== undefined) {
        query.set("limit", String(params.limit));
    }

    const response = await api.get<ChatSearchResultResponse[]>(
        `${CHATS_BASE}/search?${query.toString()}`,
    );

    return response.map((item) => ({
        id: item.id,
        title: item.title ?? undefined,
        snippet: item.snippet,
        updatedAt: item.updated_at,
    }));
};

export const fetchInternalModels = async (
    api: AuthenticatedApi,
): Promise<string[]> => api.get<string[]>("/models");

export const fetchConversationTree = async (
    api: AuthenticatedApi,
    chatId: string,
): Promise<ConversationDetailTreeResponse> =>
    api.get<ConversationDetailTreeResponse>(`/conversations/${chatId}/tree`);

export const updateMessageActiveChild = async (
    api: AuthenticatedApi,
    messageId: string,
    activeChildId?: string,
): Promise<void> => {
    await api.put(`/conversations/messages/${messageId}/active-child`, {
        active_child_id: activeChildId ?? undefined,
    });
};

interface SendMessageCallbacks {
    onChatId: (
        chatId: string,
        parentMessageId?: string,
        chatTitle?: string,
    ) => void;
    onAssistantMessage: (payload: {
        assistantMessageId: string;
        content: string;
        parentMessageId?: string;
        userMessageId?: string;
    }) => void;
    onError: (errorMessage: string) => void;
}

type ChatTitleStage = "initial" | "post_assistant";

type AgentStage = "search" | "chatbot" | "guardrails";

type AgentStageStatus = "start" | "end" | "error";

type ToolCallStatus = "start" | "end" | "error";

type ThinkingStatus = "start" | "delta" | "end";

interface AgentStageEvent {
    chatId: string;
    stage: AgentStage;
    status: AgentStageStatus;
    durationMs?: number;
    iteration?: number;
}

interface ToolCallEvent {
    chatId: string;
    stage?: AgentStage;
    status: ToolCallStatus;
    toolCallId: string;
    toolName?: string;
    toolInput?: unknown;
    toolOutput?: unknown;
    toolErrorText?: string;
    iteration?: number;
}

interface ThinkingEvent {
    chatId: string;
    status: ThinkingStatus;
    thinkingId: string;
    content?: string;
    stage?: AgentStage;
    iteration?: number;
}

interface SendMessageStreamCallbacks extends SendMessageCallbacks {
    onTitleUpdate: (
        chatId: string,
        title: string,
        stage: ChatTitleStage,
    ) => void;
    onAgentStage: (event: AgentStageEvent) => void;
    onToolCall: (event: ToolCallEvent) => void;
    onThinking: (event: ThinkingEvent) => void;
}

const parseSseEvent = (
    raw: string,
): {
    event: string;
    data: string;
} => {
    let event = "message";
    const dataLines: string[] = [];

    for (const line of raw.split("\n")) {
        if (line.startsWith("event:")) {
            event = line.slice("event:".length).trim();
        } else if (line.startsWith("data:")) {
            dataLines.push(line.slice("data:".length).trim());
        }
    }

    return {
        event,
        data: dataLines.join("\n"),
    };
};

const parseSsePayload = (data: string): Record<string, unknown> | undefined => {
    try {
        const parsed: unknown = JSON.parse(data);
        return isRecord(parsed) ? parsed : undefined;
    } catch {
        return undefined;
    }
};

const isAgentStage = (value: unknown): value is AgentStage =>
    value === "search" || value === "chatbot" || value === "guardrails";

const isAgentStageStatus = (value: unknown): value is AgentStageStatus =>
    value === "start" || value === "end" || value === "error";

const isToolCallStatus = (value: unknown): value is ToolCallStatus =>
    value === "start" || value === "end" || value === "error";

const isThinkingStatus = (value: unknown): value is ThinkingStatus =>
    value === "start" || value === "delta" || value === "end";

export const sendMessageStream = async (
    api: AuthenticatedApi,
    params: {
        userMessage: string;
        chatId?: string;
        parentMessageId?: string;
        promptSetVersionId?: string;
        modelOverrides?: ModelOverrides;
        isRegeneration?: boolean;
    },
    callbacks: SendMessageStreamCallbacks,
    signal?: AbortSignal,
): Promise<void> => {
    const body: Record<string, unknown> = {
        user_prompt: params.userMessage,
    };

    if (params.chatId !== undefined && params.parentMessageId !== undefined) {
        body.conversation_id = params.chatId;
        body.parent_message_id = params.parentMessageId;
    }
    if (
        params.promptSetVersionId !== undefined &&
        params.promptSetVersionId !== ""
    ) {
        body.prompt_set_version_id = params.promptSetVersionId;
    }
    const chatbotModel = params.modelOverrides?.chatbotModel;
    if (chatbotModel !== undefined && chatbotModel !== "") {
        body.chatbot_model = chatbotModel;
    }
    const searchModel = params.modelOverrides?.searchModel;
    if (searchModel !== undefined && searchModel !== "") {
        body.search_model = searchModel;
    }
    const guardrailModel = params.modelOverrides?.guardrailModel;
    if (guardrailModel !== undefined && guardrailModel !== "") {
        body.guardrail_model = guardrailModel;
    }
    const chatbotReasoningEffort =
        params.modelOverrides?.chatbotReasoningEffort;
    if (chatbotReasoningEffort !== undefined) {
        body.chatbot_reasoning_effort = chatbotReasoningEffort;
    }
    const searchReasoningEffort = params.modelOverrides?.searchReasoningEffort;
    if (searchReasoningEffort !== undefined) {
        body.search_reasoning_effort = searchReasoningEffort;
    }
    const guardrailReasoningEffort =
        params.modelOverrides?.guardrailReasoningEffort;
    if (guardrailReasoningEffort !== undefined) {
        body.guardrail_reasoning_effort = guardrailReasoningEffort;
    }
    if (params.isRegeneration === true) {
        body.is_regeneration = true;
    }

    const response = await api.postStream("/messages/internal/stream", body, {
        signal,
        baseUrl: API_URL,
    });

    const reader = response.body?.getReader();
    if (reader === undefined) {
        throw new Error("Missing streaming response body");
    }
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
        // eslint-disable-next-line no-await-in-loop
        const { value, done } = await reader.read();
        if (done) {
            break;
        }
        buffer += decoder.decode(value, { stream: true });
        buffer = buffer.replaceAll("\r\n", "\n");

        let splitIndex = buffer.indexOf("\n\n");
        while (splitIndex !== -1) {
            const rawEvent = buffer.slice(0, splitIndex).trim();
            buffer = buffer.slice(splitIndex + 2);
            splitIndex = buffer.indexOf("\n\n");

            if (rawEvent !== "") {
                const parsed = parseSseEvent(rawEvent);
                if (parsed.data !== "") {
                    const payload = parseSsePayload(parsed.data);
                    if (payload) {
                        switch (parsed.event) {
                            case "conversation": {
                                const chatId = payload.conversation_id;
                                if (typeof chatId === "string") {
                                    callbacks.onChatId(
                                        chatId,
                                        undefined,
                                        typeof payload.conversation_title ===
                                            "string"
                                            ? payload.conversation_title
                                            : undefined,
                                    );
                                }
                                break;
                            }
                            case "title_update": {
                                const {
                                    conversation_id: chatId,
                                    title,
                                    stage,
                                } = payload;
                                if (
                                    typeof chatId === "string" &&
                                    typeof title === "string" &&
                                    (stage === "initial" ||
                                        stage === "post_assistant")
                                ) {
                                    callbacks.onTitleUpdate(
                                        chatId,
                                        title,
                                        stage,
                                    );
                                }
                                break;
                            }
                            case "agent_stage": {
                                const {
                                    conversation_id: chatId,
                                    stage,
                                    status,
                                    duration_ms: durationMs,
                                    iteration,
                                } = payload;
                                if (
                                    typeof chatId === "string" &&
                                    isAgentStage(stage) &&
                                    isAgentStageStatus(status)
                                ) {
                                    callbacks.onAgentStage({
                                        chatId,
                                        stage,
                                        status,
                                        durationMs:
                                            typeof durationMs === "number"
                                                ? durationMs
                                                : undefined,
                                        iteration:
                                            typeof iteration === "number"
                                                ? iteration
                                                : undefined,
                                    });
                                }
                                break;
                            }
                            case "tool_call": {
                                const {
                                    conversation_id: chatId,
                                    tool_call_id: toolCallId,
                                    status,
                                    stage,
                                    tool_name: toolName,
                                    tool_input: toolInput,
                                    tool_output: toolOutput,
                                    tool_error_text: toolErrorText,
                                    iteration,
                                } = payload;
                                if (
                                    typeof chatId === "string" &&
                                    typeof toolCallId === "string" &&
                                    isToolCallStatus(status)
                                ) {
                                    callbacks.onToolCall({
                                        chatId,
                                        toolCallId,
                                        status,
                                        stage: isAgentStage(stage)
                                            ? stage
                                            : undefined,
                                        toolName:
                                            typeof toolName === "string"
                                                ? toolName
                                                : undefined,
                                        toolInput,
                                        toolOutput,
                                        toolErrorText:
                                            typeof toolErrorText === "string"
                                                ? toolErrorText
                                                : undefined,
                                        iteration:
                                            typeof iteration === "number"
                                                ? iteration
                                                : undefined,
                                    });
                                }
                                break;
                            }
                            case "thinking": {
                                const {
                                    conversation_id: chatId,
                                    status,
                                    thinking_id: thinkingId,
                                    content,
                                    stage,
                                    iteration,
                                } = payload;
                                if (
                                    typeof chatId === "string" &&
                                    typeof thinkingId === "string" &&
                                    isThinkingStatus(status)
                                ) {
                                    callbacks.onThinking({
                                        chatId,
                                        status,
                                        thinkingId,
                                        content:
                                            typeof content === "string"
                                                ? content
                                                : undefined,
                                        stage: isAgentStage(stage)
                                            ? stage
                                            : undefined,
                                        iteration:
                                            typeof iteration === "number"
                                                ? iteration
                                                : undefined,
                                    });
                                }
                                break;
                            }
                            case "assistant_message": {
                                const messageId = payload.assistant_message_id;
                                const content = payload.assistant_message;
                                const parentMessageId =
                                    payload.parent_message_id;
                                const userMessageId = payload.user_message_id;
                                if (
                                    typeof messageId === "string" &&
                                    typeof content === "string"
                                ) {
                                    callbacks.onAssistantMessage({
                                        assistantMessageId: messageId,
                                        content,
                                        parentMessageId:
                                            typeof parentMessageId === "string"
                                                ? parentMessageId
                                                : undefined,
                                        userMessageId:
                                            typeof userMessageId === "string"
                                                ? userMessageId
                                                : undefined,
                                    });
                                }
                                break;
                            }
                            case "error": {
                                const { message } = payload;
                                if (typeof message === "string") {
                                    callbacks.onError(message);
                                }
                                break;
                            }
                            default: {
                                break;
                            }
                        }
                    }
                }
            }
        }
    }
};

export const fetchMessageFeedback = async (
    api: AuthenticatedApi,
    messageId: string,
): Promise<MessageFeedback[]> =>
    api
        .get<
            (Omit<MessageFeedback, "text"> & { text: string | null })[]
        >(`/conversations/messages/${messageId}/feedback`)
        .then((items) =>
            items.map((item) => ({
                ...item,
                text: item.text ?? undefined,
            })),
        );

export const submitMessageFeedback = async (
    api: AuthenticatedApi,
    messageId: string,
    feedback: {
        rating: Rating;
        text?: string;
    },
): Promise<MessageFeedback> =>
    api
        .post<Omit<MessageFeedback, "text"> & { text: string | null }>(
            `/conversations/messages/${messageId}/feedback`,
            {
                rating: feedback.rating,
                ...(feedback.text === undefined ? {} : { text: feedback.text }),
            },
        )
        .then((item) => ({
            ...item,
            text: item.text ?? undefined,
        }));

export const deleteMessageFeedback = async (
    api: AuthenticatedApi,
    feedbackId: string,
): Promise<void> => {
    await api.delete(`/conversations/messages/feedback/${feedbackId}`);
};
