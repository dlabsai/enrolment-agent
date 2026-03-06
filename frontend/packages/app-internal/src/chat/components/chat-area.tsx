import { Chat } from "@va/shared/components/chat";
import { LoadingIndicator } from "@va/shared/components/loading-indicator";
import { Button } from "@va/shared/components/ui/button";
import {
    Dialog,
    DialogContent,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@va/shared/components/ui/dialog";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@va/shared/components/ui/select";
import {
    Sheet,
    SheetContent,
    SheetDescription,
    SheetHeader,
    SheetTitle,
} from "@va/shared/components/ui/sheet";
import { Textarea } from "@va/shared/components/ui/textarea";
import {
    Tooltip,
    TooltipContent,
    TooltipTrigger,
} from "@va/shared/components/ui/tooltip";
import type { ChatMessage } from "@va/shared/types";
import {
    Activity,
    ChevronLeft,
    ChevronRight,
    Copy,
    ListTree,
    Pencil,
    RefreshCw,
    SlidersHorizontal,
} from "lucide-react";
import { type JSX, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { useAuthenticatedApi } from "../../auth/hooks/use-authenticated-api";
import { ModelSelectionDialogContent } from "../../components/model-selection-dialog-content";
import { TraceTurnDebugView } from "../../traces/components/trace-turn-debug-view";
import { useTraceDetailByMessage } from "../../traces/hooks/use-trace-detail-by-message";
import { useChatActions, useChatStore } from "../contexts/chat-store-context";
import { fetchInternalModels } from "../lib/api";
import {
    selectCurrentChat,
    selectCurrentDraft,
    selectIsCurrentLoading,
} from "../lib/store";
import type { Message, ModelOverrides } from "../types";
import { MessageFeedback } from "./message-feedback";

const convertToChatMessages = (
    messages: Message[],
): {
    id: string;
    role: Message["role"];
    content: string;
    timestamp: number;
}[] =>
    messages.map((message) => ({
        id: message.id,
        role: message.role,
        content: message.content,
        timestamp: message.createdAt,
    }));

interface ChatAreaProps {
    canSendMessages?: boolean;
}

const HIDE_MESSAGE_ACTIONS_UNTIL_HOVER = false;
const ENABLE_CHAT_MODEL_SELECTOR =
    (import.meta.env.VITE_ENABLE_CHAT_MODEL_SELECTOR ?? "true") === "true";
const DEFAULT_REASONING_EFFORT_VALUE = "__default_reasoning__";
const DEFAULT_PRESET_VALUE = "__default_preset__";
const COMMAND_UNSELECTED_VALUE = "__va_model_unselected__";
const MODEL_CONFIG_STORAGE_KEY = "va.internal.chat.model-config";
const MODEL_FAVORITES_STORAGE_KEY = "va.internal.chat.model-favorites";
const MODEL_PRESETS_STORAGE_KEY = "va.internal.chat.model-presets";
type ModelTarget = "search" | "chatbot" | "guardrails";
const MODEL_TARGET_TABS: { value: ModelTarget; label: string }[] = [
    { value: "search", label: "Search" },
    { value: "chatbot", label: "Chatbot" },
    { value: "guardrails", label: "Guardrails" },
];

type ReasoningEffort = "none" | "low" | "medium" | "high" | "xhigh";

type Gpt5Series = "5" | "5.1" | "5.2";

const REASONING_EFFORT_OPTIONS: Record<Gpt5Series, ReasoningEffort[]> = {
    "5": ["low", "medium", "high"],
    "5.1": ["none", "low", "medium", "high"],
    "5.2": ["none", "low", "medium", "high", "xhigh"],
};

const getGpt5Series = (model: string): Gpt5Series | undefined => {
    const match = /gpt-5(?:\.(?<minor>1|2))?/u.exec(model);
    if (!match) {
        return undefined;
    }
    if (match.groups?.minor === "1") {
        return "5.1";
    }
    if (match.groups?.minor === "2") {
        return "5.2";
    }
    return "5";
};

const getReasoningEffortOptions = (model: string): ReasoningEffort[] => {
    const series = getGpt5Series(model);
    if (!series) {
        return [];
    }
    return REASONING_EFFORT_OPTIONS[series];
};

const isReasoningEffort = (value: string): value is ReasoningEffort =>
    value === "none" ||
    value === "low" ||
    value === "medium" ||
    value === "high" ||
    value === "xhigh";

const isReasoningEffortSupported = (
    model: string,
    effort: ReasoningEffort | "",
): effort is ReasoningEffort =>
    effort !== "" && getReasoningEffortOptions(model).includes(effort);

const isRecord = (value: unknown): value is Record<string, unknown> =>
    typeof value === "object" && value !== null;

const getReasoningEffortLabel = (effort: ReasoningEffort): string => {
    if (effort === "xhigh") {
        return "Extra high";
    }
    return effort.charAt(0).toUpperCase() + effort.slice(1);
};

const copyMessageToClipboard = async (content: string): Promise<void> => {
    try {
        await navigator.clipboard.writeText(content);
        toast.success("Copied message");
    } catch {
        toast.error("Failed to copy message");
    }
};

interface StoredModelConfig {
    chatbotModel?: string;
    searchModel?: string;
    guardrailModel?: string;
    chatbotReasoningEffort?: string;
    searchReasoningEffort?: string;
    guardrailReasoningEffort?: string;
}

const readStoredModelConfig = (): StoredModelConfig | undefined => {
    if (typeof window === "undefined") {
        return undefined;
    }
    const stored = window.localStorage.getItem(MODEL_CONFIG_STORAGE_KEY);
    if (stored === null || stored === "") {
        return undefined;
    }
    try {
        const parsed: unknown = JSON.parse(stored);
        if (typeof parsed !== "object" || parsed === null) {
            return undefined;
        }
        const safeParsed: StoredModelConfig = {};
        if (
            "chatbotModel" in parsed &&
            typeof parsed.chatbotModel === "string"
        ) {
            safeParsed.chatbotModel = parsed.chatbotModel;
        }
        if ("searchModel" in parsed && typeof parsed.searchModel === "string") {
            safeParsed.searchModel = parsed.searchModel;
        }
        if (
            "guardrailModel" in parsed &&
            typeof parsed.guardrailModel === "string"
        ) {
            safeParsed.guardrailModel = parsed.guardrailModel;
        }
        if (
            "chatbotReasoningEffort" in parsed &&
            typeof parsed.chatbotReasoningEffort === "string"
        ) {
            safeParsed.chatbotReasoningEffort = parsed.chatbotReasoningEffort;
        }
        if (
            "searchReasoningEffort" in parsed &&
            typeof parsed.searchReasoningEffort === "string"
        ) {
            safeParsed.searchReasoningEffort = parsed.searchReasoningEffort;
        }
        if (
            "guardrailReasoningEffort" in parsed &&
            typeof parsed.guardrailReasoningEffort === "string"
        ) {
            safeParsed.guardrailReasoningEffort =
                parsed.guardrailReasoningEffort;
        }
        return safeParsed;
    } catch {
        window.localStorage.removeItem(MODEL_CONFIG_STORAGE_KEY);
        return undefined;
    }
};

interface ModelPreset {
    name: string;
    chatbotModel?: string;
    searchModel?: string;
    guardrailModel?: string;
    chatbotReasoningEffort?: ReasoningEffort;
    searchReasoningEffort?: ReasoningEffort;
    guardrailReasoningEffort?: ReasoningEffort;
}

const readStoredModelFavorites = (): string[] => {
    if (typeof window === "undefined") {
        return [];
    }
    const stored = window.localStorage.getItem(MODEL_FAVORITES_STORAGE_KEY);
    if (stored === null || stored === "") {
        return [];
    }
    try {
        const parsed: unknown = JSON.parse(stored);
        if (!Array.isArray(parsed)) {
            return [];
        }
        const favorites = parsed
            .filter((item): item is string => typeof item === "string")
            .map((item) => item.trim())
            .filter((item) => item !== "");
        return [...new Set(favorites)];
    } catch {
        window.localStorage.removeItem(MODEL_FAVORITES_STORAGE_KEY);
        return [];
    }
};

const readStoredModelPresets = (): ModelPreset[] => {
    if (typeof window === "undefined") {
        return [];
    }
    const stored = window.localStorage.getItem(MODEL_PRESETS_STORAGE_KEY);
    if (stored === null || stored === "") {
        return [];
    }
    try {
        const parsed: unknown = JSON.parse(stored);
        if (!Array.isArray(parsed)) {
            return [];
        }
        const presets: ModelPreset[] = [];
        for (const entry of parsed) {
            if (isRecord(entry)) {
                const nameValue = entry.name;
                const name =
                    typeof nameValue === "string" ? nameValue.trim() : "";
                if (name !== "") {
                    const preset: ModelPreset = { name };
                    const { chatbotModel } = entry;
                    if (
                        typeof chatbotModel === "string" &&
                        chatbotModel !== ""
                    ) {
                        preset.chatbotModel = chatbotModel;
                    }
                    const { searchModel } = entry;
                    if (typeof searchModel === "string" && searchModel !== "") {
                        preset.searchModel = searchModel;
                    }
                    const { guardrailModel } = entry;
                    if (
                        typeof guardrailModel === "string" &&
                        guardrailModel !== ""
                    ) {
                        preset.guardrailModel = guardrailModel;
                    }
                    const { chatbotReasoningEffort } = entry;
                    if (
                        typeof chatbotReasoningEffort === "string" &&
                        isReasoningEffort(chatbotReasoningEffort)
                    ) {
                        preset.chatbotReasoningEffort = chatbotReasoningEffort;
                    }
                    const { searchReasoningEffort } = entry;
                    if (
                        typeof searchReasoningEffort === "string" &&
                        isReasoningEffort(searchReasoningEffort)
                    ) {
                        preset.searchReasoningEffort = searchReasoningEffort;
                    }
                    const { guardrailReasoningEffort } = entry;
                    if (
                        typeof guardrailReasoningEffort === "string" &&
                        isReasoningEffort(guardrailReasoningEffort)
                    ) {
                        preset.guardrailReasoningEffort =
                            guardrailReasoningEffort;
                    }
                    presets.push(preset);
                }
            }
        }
        return presets;
    } catch {
        window.localStorage.removeItem(MODEL_PRESETS_STORAGE_KEY);
        return [];
    }
};

export const ChatArea = ({
    canSendMessages = true,
}: ChatAreaProps): JSX.Element => {
    const api = useAuthenticatedApi();
    const currentChatId = useChatStore((state) => state.currentChatId);
    const currentChat = useChatStore(selectCurrentChat);
    const isLoading = useChatStore(selectIsCurrentLoading);
    const draft = useChatStore(selectCurrentDraft);
    const conversationTree = useChatStore((state) =>
        currentChatId === undefined
            ? undefined
            : state.conversationTrees.get(currentChatId),
    );

    const [availableModels, setAvailableModels] = useState<string[]>([]);
    const [modelsLoading, setModelsLoading] = useState(
        ENABLE_CHAT_MODEL_SELECTOR,
    );
    const [modelsError, setModelsError] = useState<string | undefined>();
    const [commandValue, setCommandValue] = useState(COMMAND_UNSELECTED_VALUE);
    const [chatbotModel, setChatbotModel] = useState(() => {
        const stored = readStoredModelConfig();
        return typeof stored?.chatbotModel === "string"
            ? stored.chatbotModel
            : "";
    });
    const [searchModel, setSearchModel] = useState(() => {
        const stored = readStoredModelConfig();
        return typeof stored?.searchModel === "string"
            ? stored.searchModel
            : "";
    });
    const [guardrailModel, setGuardrailModel] = useState(() => {
        const stored = readStoredModelConfig();
        return typeof stored?.guardrailModel === "string"
            ? stored.guardrailModel
            : "";
    });
    const [chatbotReasoningEffort, setChatbotReasoningEffort] = useState<
        ReasoningEffort | ""
    >(() => {
        const stored = readStoredModelConfig();
        if (
            typeof stored?.chatbotReasoningEffort === "string" &&
            isReasoningEffort(stored.chatbotReasoningEffort)
        ) {
            return stored.chatbotReasoningEffort;
        }
        return "";
    });
    const [searchReasoningEffort, setSearchReasoningEffort] = useState<
        ReasoningEffort | ""
    >(() => {
        const stored = readStoredModelConfig();
        if (
            typeof stored?.searchReasoningEffort === "string" &&
            isReasoningEffort(stored.searchReasoningEffort)
        ) {
            return stored.searchReasoningEffort;
        }
        return "";
    });
    const [guardrailReasoningEffort, setGuardrailReasoningEffort] = useState<
        ReasoningEffort | ""
    >(() => {
        const stored = readStoredModelConfig();
        if (
            typeof stored?.guardrailReasoningEffort === "string" &&
            isReasoningEffort(stored.guardrailReasoningEffort)
        ) {
            return stored.guardrailReasoningEffort;
        }
        return "";
    });
    const [favoriteModels, setFavoriteModels] = useState(() =>
        readStoredModelFavorites(),
    );
    const [modelPresets, setModelPresets] = useState(() =>
        readStoredModelPresets(),
    );
    const [presetName, setPresetName] = useState("");
    const [deletePresetOpen, setDeletePresetOpen] = useState(false);
    const [deletePresetName, setDeletePresetName] = useState<
        string | undefined
    >();
    const [isModelDialogOpen, setIsModelDialogOpen] = useState(false);
    const [isModelTooltipOpen, setIsModelTooltipOpen] = useState(false);
    const [modelTarget, setModelTarget] = useState<ModelTarget>("chatbot");

    const [editDialogOpen, setEditDialogOpen] = useState(false);
    const [editValue, setEditValue] = useState("");
    const [editMessageId, setEditMessageId] = useState<string | undefined>();

    const [tracePanelOpen, setTracePanelOpen] = useState(false);
    const [traceMessageId, setTraceMessageId] = useState<string | undefined>();
    const {
        detail: traceDetail,
        loading: traceLoading,
        error: traceError,
    } = useTraceDetailByMessage(traceMessageId);

    useEffect(() => {
        if (!ENABLE_CHAT_MODEL_SELECTOR || typeof window === "undefined") {
            return;
        }

        const payload = {
            chatbotModel,
            searchModel,
            guardrailModel,
            chatbotReasoningEffort:
                chatbotReasoningEffort === ""
                    ? undefined
                    : chatbotReasoningEffort,
            searchReasoningEffort:
                searchReasoningEffort === ""
                    ? undefined
                    : searchReasoningEffort,
            guardrailReasoningEffort:
                guardrailReasoningEffort === ""
                    ? undefined
                    : guardrailReasoningEffort,
        };

        window.localStorage.setItem(
            MODEL_CONFIG_STORAGE_KEY,
            JSON.stringify(payload),
        );
    }, [
        chatbotModel,
        chatbotReasoningEffort,
        guardrailModel,
        guardrailReasoningEffort,
        searchModel,
        searchReasoningEffort,
    ]);

    useEffect(() => {
        if (!ENABLE_CHAT_MODEL_SELECTOR || typeof window === "undefined") {
            return;
        }

        window.localStorage.setItem(
            MODEL_FAVORITES_STORAGE_KEY,
            JSON.stringify(favoriteModels),
        );
    }, [favoriteModels]);

    useEffect(() => {
        if (!ENABLE_CHAT_MODEL_SELECTOR || typeof window === "undefined") {
            return;
        }

        window.localStorage.setItem(
            MODEL_PRESETS_STORAGE_KEY,
            JSON.stringify(modelPresets),
        );
    }, [modelPresets]);

    useEffect((): (() => void) | undefined => {
        if (!ENABLE_CHAT_MODEL_SELECTOR) {
            return undefined;
        }

        let mounted = true;
        void fetchInternalModels(api)
            .then((models) => {
                if (!mounted) {
                    return;
                }
                const uniqueModels = [
                    ...new Set(
                        models
                            .map((model) => model.trim())
                            .filter((model) => model !== ""),
                    ),
                ];
                setAvailableModels(uniqueModels);
            })
            .catch((error: unknown) => {
                if (!mounted) {
                    return;
                }
                setModelsError(
                    error instanceof Error
                        ? error.message
                        : "Failed to load models",
                );
            })
            .finally(() => {
                if (!mounted) {
                    return;
                }
                setModelsLoading(false);
            });

        return () => {
            mounted = false;
        };
    }, [api]);

    const messages = useMemo(
        () =>
            convertToChatMessages(
                currentChat === undefined ? [] : currentChat.messages,
            ),
        [currentChat],
    );

    const messageById = useMemo(() => {
        const map = new Map<string, Message>();
        if (currentChat) {
            for (const message of currentChat.messages) {
                map.set(message.id, message);
            }
        }
        return map;
    }, [currentChat]);

    const firstUserMessageId = useMemo(() => {
        const firstUser = currentChat?.messages.find(
            (message) => message.role === "user",
        );
        return firstUser?.id;
    }, [currentChat]);

    const activeChildByParent = useMemo(() => {
        const map = new Map<string, string>();
        const path = conversationTree?.currentBranchPath ?? [];
        for (let index = 0; index < path.length - 1; index += 1) {
            map.set(path[index], path[index + 1]);
        }
        return map;
    }, [conversationTree?.currentBranchPath]);

    const loadingActivity = currentChat?.loadingActivity ?? [];
    const loadingActivityLog = currentChat?.loadingActivityLog ?? [];

    const messageActivityLog = useChatStore(
        (state) => state.messageActivityLog,
    );
    const messageActivityLogLoading = useChatStore(
        (state) => state.messageActivityLogLoading,
    );

    const [openActivityMessageIdsByChat, setOpenActivityMessageIdsByChat] =
        useState(() => new Map<string, Set<string>>());
    const chatActivityKey = currentChatId ?? "__new__";
    const openActivityMessageIds = useMemo(
        () => openActivityMessageIdsByChat.get(chatActivityKey) ?? new Set(),
        [chatActivityKey, openActivityMessageIdsByChat],
    );

    const messagesInitialized = useMemo(() => {
        if (currentChatId === undefined) {
            return true;
        }
        if (currentChatId.startsWith("__temp_")) {
            return true;
        }
        if (currentChat === undefined) {
            return false;
        }
        return currentChat.messages.length > 0;
    }, [currentChatId, currentChat]);

    const { sendMessage, setDraft, loadMessageActivityLog, setActiveChild } =
        useChatActions();

    const modelOverrides = useMemo((): ModelOverrides | undefined => {
        const overrides: ModelOverrides = {};
        if (chatbotModel !== "") {
            overrides.chatbotModel = chatbotModel;
        }
        if (searchModel !== "") {
            overrides.searchModel = searchModel;
        }
        if (guardrailModel !== "") {
            overrides.guardrailModel = guardrailModel;
        }
        if (isReasoningEffortSupported(chatbotModel, chatbotReasoningEffort)) {
            overrides.chatbotReasoningEffort = chatbotReasoningEffort;
        }
        if (isReasoningEffortSupported(searchModel, searchReasoningEffort)) {
            overrides.searchReasoningEffort = searchReasoningEffort;
        }
        if (
            isReasoningEffortSupported(guardrailModel, guardrailReasoningEffort)
        ) {
            overrides.guardrailReasoningEffort = guardrailReasoningEffort;
        }
        return Object.keys(overrides).length > 0 ? overrides : undefined;
    }, [
        chatbotModel,
        chatbotReasoningEffort,
        guardrailModel,
        guardrailReasoningEffort,
        searchModel,
        searchReasoningEffort,
    ]);

    const handleSendMessage = (content: string): void => {
        void sendMessage(content, modelOverrides);
    };

    const editTargetMessage =
        editMessageId === undefined
            ? undefined
            : messageById.get(editMessageId);

    const handleEditMessage = (message: Message): void => {
        setEditMessageId(message.id);
        setEditValue(message.content);
        setEditDialogOpen(true);
    };

    const handleEditSave = (): void => {
        if (!editTargetMessage) {
            return;
        }
        const trimmed = editValue.trim();
        if (trimmed === "") {
            toast.error("Message cannot be empty");
            return;
        }
        const parentMessageId = editTargetMessage.parentId;
        void sendMessage(trimmed, modelOverrides, {
            parentMessageId,
            trimToMessageId: parentMessageId ?? editTargetMessage.id,
        });
        setEditDialogOpen(false);
    };

    const handleRegenerateMessage = (message: Message): void => {
        if (message.parentId === undefined) {
            toast.error("Missing parent message");
            return;
        }
        const parentMessage = messageById.get(message.parentId);
        if (!parentMessage) {
            toast.error("Missing parent message");
            return;
        }
        void sendMessage(parentMessage.content, modelOverrides, {
            parentMessageId: message.parentId,
            isRegeneration: true,
            trimToMessageId: message.parentId,
        });
    };

    const handleSwitchBranch = async (
        messageId: string,
        nextChildId: string,
    ): Promise<void> => {
        if (currentChatId === undefined) {
            return;
        }
        try {
            await setActiveChild(currentChatId, messageId, nextChildId);
        } catch {
            toast.error("Failed to switch branch");
        }
    };

    const openTracePanel = (messageId: string): void => {
        setTraceMessageId(messageId);
        setTracePanelOpen(true);
    };

    const selectorDisabled = !ENABLE_CHAT_MODEL_SELECTOR;
    const childrenByParent = conversationTree?.childrenByParent;
    const messageActionsDisabled = !canSendMessages || isLoading;
    const hasTraceMessageId =
        traceMessageId !== undefined && traceMessageId.trim() !== "";

    const renderBranchSwitcher = (
        parentMessageId: string | undefined,
        currentMessageId: string,
    ): JSX.Element | undefined => {
        if (parentMessageId === undefined) {
            return undefined;
        }

        const siblings = childrenByParent?.get(parentMessageId);
        if (!siblings || siblings.length < 2) {
            return undefined;
        }

        const lastSibling = siblings.at(-1);
        if (lastSibling === undefined) {
            return undefined;
        }

        const fallbackChildId =
            activeChildByParent.get(parentMessageId) ?? lastSibling;
        const currentIndex = siblings.indexOf(currentMessageId);
        const fallbackIndex = siblings.indexOf(fallbackChildId);
        const resolvedIndex =
            currentIndex === -1
                ? fallbackIndex === -1
                    ? siblings.length - 1
                    : fallbackIndex
                : currentIndex;
        const isFirst = resolvedIndex <= 0;
        const isLast = resolvedIndex >= siblings.length - 1;
        const previousChild = siblings[Math.max(resolvedIndex - 1, 0)];
        const nextChild =
            siblings[Math.min(resolvedIndex + 1, siblings.length - 1)];

        return (
            <div className="text-muted-foreground flex items-center gap-1 text-xs">
                <button
                    aria-label="Previous branch"
                    className="hover:text-foreground disabled:opacity-40"
                    disabled={messageActionsDisabled || isFirst}
                    onClick={() => {
                        void handleSwitchBranch(parentMessageId, previousChild);
                    }}
                    type="button"
                >
                    <ChevronLeft className="size-3" />
                </button>
                <span>
                    {resolvedIndex + 1} / {siblings.length}
                </span>
                <button
                    aria-label="Next branch"
                    className="hover:text-foreground disabled:opacity-40"
                    disabled={messageActionsDisabled || isLast}
                    onClick={() => {
                        void handleSwitchBranch(parentMessageId, nextChild);
                    }}
                    type="button"
                >
                    <ChevronRight className="size-3" />
                </button>
            </div>
        );
    };

    const favoriteModelsAvailable = useMemo(
        () => favoriteModels.filter((model) => availableModels.includes(model)),
        [favoriteModels, availableModels],
    );

    const favoriteModelSet = useMemo(
        () => new Set(favoriteModelsAvailable),
        [favoriteModelsAvailable],
    );

    const sortedFavoriteModels = useMemo(
        () =>
            favoriteModelsAvailable.toSorted((left, right) =>
                left.localeCompare(right),
            ),
        [favoriteModelsAvailable],
    );

    const groupedModels = useMemo(() => {
        const groups = new Map<string, string[]>();
        for (const model of availableModels) {
            if (!favoriteModelSet.has(model)) {
                const separatorIndex = model.indexOf(":");
                const provider =
                    separatorIndex > 0
                        ? model.slice(0, separatorIndex)
                        : "default";
                const name =
                    separatorIndex > 0
                        ? model.slice(separatorIndex + 1)
                        : model;
                const entries = groups.get(provider) ?? [];
                entries.push(name);
                groups.set(provider, entries);
            }
        }
        return [...groups.entries()].map(([provider, models]) => ({
            provider,
            models: models.toSorted((left, right) => left.localeCompare(right)),
        }));
    }, [availableModels, favoriteModelSet]);

    const hasOverrides =
        chatbotModel !== "" ||
        searchModel !== "" ||
        guardrailModel !== "" ||
        isReasoningEffortSupported(chatbotModel, chatbotReasoningEffort) ||
        isReasoningEffortSupported(searchModel, searchReasoningEffort) ||
        isReasoningEffortSupported(guardrailModel, guardrailReasoningEffort);

    const overrideSummary = useMemo((): string[] => {
        const summarize = (
            label: string,
            model: string,
            reasoningEffort: ReasoningEffort | "",
        ): string | undefined => {
            if (model === "" && reasoningEffort === "") {
                return undefined;
            }
            const parts: string[] = [];
            if (model !== "") {
                parts.push(model);
            }
            if (isReasoningEffortSupported(model, reasoningEffort)) {
                parts.push(`effort ${reasoningEffort}`);
            }
            if (parts.length === 0) {
                return undefined;
            }
            return `${label}: ${parts.join(", ")}`;
        };

        return [
            summarize("Search", searchModel, searchReasoningEffort),
            summarize("Chatbot", chatbotModel, chatbotReasoningEffort),
            summarize("Guardrails", guardrailModel, guardrailReasoningEffort),
        ].filter((value): value is string => value !== undefined);
    }, [
        chatbotModel,
        chatbotReasoningEffort,
        guardrailModel,
        guardrailReasoningEffort,
        searchModel,
        searchReasoningEffort,
    ]);

    const normalizedChatbotEffort = isReasoningEffortSupported(
        chatbotModel,
        chatbotReasoningEffort,
    )
        ? chatbotReasoningEffort
        : "";
    const normalizedSearchEffort = isReasoningEffortSupported(
        searchModel,
        searchReasoningEffort,
    )
        ? searchReasoningEffort
        : "";
    const normalizedGuardrailEffort = isReasoningEffortSupported(
        guardrailModel,
        guardrailReasoningEffort,
    )
        ? guardrailReasoningEffort
        : "";

    const activePresetName = useMemo(() => {
        for (const preset of modelPresets) {
            const presetChatbotEffort = isReasoningEffortSupported(
                preset.chatbotModel ?? "",
                preset.chatbotReasoningEffort ?? "",
            )
                ? (preset.chatbotReasoningEffort ?? "")
                : "";
            const presetSearchEffort = isReasoningEffortSupported(
                preset.searchModel ?? "",
                preset.searchReasoningEffort ?? "",
            )
                ? (preset.searchReasoningEffort ?? "")
                : "";
            const presetGuardrailEffort = isReasoningEffortSupported(
                preset.guardrailModel ?? "",
                preset.guardrailReasoningEffort ?? "",
            )
                ? (preset.guardrailReasoningEffort ?? "")
                : "";

            if (
                (preset.chatbotModel ?? "") === chatbotModel &&
                (preset.searchModel ?? "") === searchModel &&
                (preset.guardrailModel ?? "") === guardrailModel &&
                presetChatbotEffort === normalizedChatbotEffort &&
                presetSearchEffort === normalizedSearchEffort &&
                presetGuardrailEffort === normalizedGuardrailEffort
            ) {
                return preset.name;
            }
        }
        return "";
    }, [
        chatbotModel,
        guardrailModel,
        modelPresets,
        normalizedChatbotEffort,
        normalizedGuardrailEffort,
        normalizedSearchEffort,
        searchModel,
    ]);

    const sortedPresets = useMemo(
        () =>
            [...modelPresets].toSorted((left, right) =>
                left.name.localeCompare(right.name),
            ),
        [modelPresets],
    );

    const presetSelectValue =
        activePresetName === "" ? DEFAULT_PRESET_VALUE : activePresetName;

    const buildPresetFromCurrent = (name: string): ModelPreset => {
        const preset: ModelPreset = { name };
        if (chatbotModel !== "") {
            preset.chatbotModel = chatbotModel;
        }
        if (searchModel !== "") {
            preset.searchModel = searchModel;
        }
        if (guardrailModel !== "") {
            preset.guardrailModel = guardrailModel;
        }
        if (isReasoningEffortSupported(chatbotModel, chatbotReasoningEffort)) {
            preset.chatbotReasoningEffort = chatbotReasoningEffort;
        }
        if (isReasoningEffortSupported(searchModel, searchReasoningEffort)) {
            preset.searchReasoningEffort = searchReasoningEffort;
        }
        if (
            isReasoningEffortSupported(guardrailModel, guardrailReasoningEffort)
        ) {
            preset.guardrailReasoningEffort = guardrailReasoningEffort;
        }
        return preset;
    };

    const applyPreset = (preset: ModelPreset): void => {
        setChatbotModel(preset.chatbotModel ?? "");
        setSearchModel(preset.searchModel ?? "");
        setGuardrailModel(preset.guardrailModel ?? "");
        setChatbotReasoningEffort(preset.chatbotReasoningEffort ?? "");
        setSearchReasoningEffort(preset.searchReasoningEffort ?? "");
        setGuardrailReasoningEffort(preset.guardrailReasoningEffort ?? "");
    };

    const handlePresetSelect = (value: string): void => {
        if (value === DEFAULT_PRESET_VALUE) {
            return;
        }
        const preset = modelPresets.find((entry) => entry.name === value);
        if (!preset) {
            return;
        }
        applyPreset(preset);
    };

    const handleSavePreset = (): void => {
        const trimmed = presetName.trim();
        if (trimmed === "") {
            toast.error("Preset name is required");
            return;
        }
        const nextPreset = buildPresetFromCurrent(trimmed);
        setModelPresets((current) => {
            const withoutExisting = current.filter(
                (preset) => preset.name !== trimmed,
            );
            return [...withoutExisting, nextPreset];
        });
        setPresetName("");
        toast.success(`Saved preset "${trimmed}"`);
    };

    const openDeletePresetDialog = (name: string): void => {
        const existing = modelPresets.find((preset) => preset.name === name);
        if (!existing) {
            return;
        }
        setDeletePresetName(name);
        setDeletePresetOpen(true);
    };

    const handleDeletePreset = (): void => {
        const name = deletePresetName;
        if (name === undefined || name === "") {
            return;
        }
        setModelPresets((current) =>
            current.filter((preset) => preset.name !== name),
        );
        setDeletePresetOpen(false);
        setDeletePresetName(undefined);
        toast.success(`Deleted preset "${name}"`);
    };

    const setModelForTarget = (value: string): void => {
        const normalizedValue = value === "" ? "" : value;
        if (modelTarget === "search") {
            setSearchModel(normalizedValue);
            return;
        }
        if (modelTarget === "guardrails") {
            setGuardrailModel(normalizedValue);
            return;
        }
        setChatbotModel(normalizedValue);
    };

    const currentTargetValue =
        modelTarget === "search"
            ? searchModel
            : modelTarget === "guardrails"
              ? guardrailModel
              : chatbotModel;

    const currentReasoningEffort =
        modelTarget === "search"
            ? searchReasoningEffort
            : modelTarget === "guardrails"
              ? guardrailReasoningEffort
              : chatbotReasoningEffort;

    const availableReasoningEfforts =
        getReasoningEffortOptions(currentTargetValue);
    const isGpt5Target = availableReasoningEfforts.length > 0;
    const normalizedReasoningEffort = isReasoningEffortSupported(
        currentTargetValue,
        currentReasoningEffort,
    )
        ? currentReasoningEffort
        : "";

    const setReasoningEffortForTarget = (value: string): void => {
        const normalizedValue =
            value === DEFAULT_REASONING_EFFORT_VALUE || value === ""
                ? ""
                : isReasoningEffort(value)
                  ? value
                  : "";
        if (!isReasoningEffortSupported(currentTargetValue, normalizedValue)) {
            if (modelTarget === "search") {
                setSearchReasoningEffort("");
                return;
            }
            if (modelTarget === "guardrails") {
                setGuardrailReasoningEffort("");
                return;
            }
            setChatbotReasoningEffort("");
            return;
        }
        if (modelTarget === "search") {
            setSearchReasoningEffort(normalizedValue);
            return;
        }
        if (modelTarget === "guardrails") {
            setGuardrailReasoningEffort(normalizedValue);
            return;
        }
        setChatbotReasoningEffort(normalizedValue);
    };

    const resetCurrentTarget = (): void => {
        setModelForTarget("");
        setReasoningEffortForTarget(DEFAULT_REASONING_EFFORT_VALUE);
    };

    const toggleFavoriteModel = (model: string): void => {
        setFavoriteModels((current) => {
            if (current.includes(model)) {
                return current.filter((entry) => entry !== model);
            }
            return [...current, model];
        });
    };

    const modelActionsAccessory = ENABLE_CHAT_MODEL_SELECTOR ? (
        <Dialog
            onOpenChange={(nextOpen) => {
                setIsModelDialogOpen(nextOpen);
                setIsModelTooltipOpen(false);
                if (nextOpen) {
                    setCommandValue(COMMAND_UNSELECTED_VALUE);
                }
            }}
            open={isModelDialogOpen}
        >
            <Tooltip
                onOpenChange={(nextOpen) => {
                    if (isModelDialogOpen) {
                        return;
                    }
                    setIsModelTooltipOpen(nextOpen);
                }}
                open={!isModelDialogOpen && isModelTooltipOpen}
            >
                <TooltipTrigger asChild>
                    <div className="flex border border-transparent">
                        <DialogTrigger asChild>
                            <Button
                                aria-label="Choose models"
                                className="relative rounded-full"
                                disabled={selectorDisabled}
                                size="icon"
                                type="button"
                                variant="ghost"
                            >
                                <SlidersHorizontal className="size-4" />
                                {hasOverrides && (
                                    <span className="bg-primary absolute -top-0.5 -right-0.5 size-2 rounded-full" />
                                )}
                            </Button>
                        </DialogTrigger>
                    </div>
                </TooltipTrigger>
                <TooltipContent
                    side="top"
                    sideOffset={4}
                >
                    {hasOverrides ? (
                        <div className="flex flex-col gap-1">
                            <p>Model overrides</p>
                            {overrideSummary.map((summary) => (
                                <p key={summary}>{summary}</p>
                            ))}
                        </div>
                    ) : (
                        <p>Model selection</p>
                    )}
                </TooltipContent>
            </Tooltip>
            <ModelSelectionDialogContent
                commandValue={commandValue}
                currentTargetValue={currentTargetValue}
                defaultPresetValue={DEFAULT_PRESET_VALUE}
                deletePresetName={deletePresetName}
                deletePresetOpen={deletePresetOpen}
                dialogContentProps={{
                    onCloseAutoFocus: (event) => {
                        event.preventDefault();
                    },
                }}
                extraSection={
                    isGpt5Target ? (
                        <div className="flex flex-col gap-1">
                            <span className="text-muted-foreground text-xs">
                                Reasoning effort
                            </span>
                            <Select
                                onValueChange={(value) => {
                                    setReasoningEffortForTarget(value);
                                }}
                                value={
                                    normalizedReasoningEffort === ""
                                        ? DEFAULT_REASONING_EFFORT_VALUE
                                        : normalizedReasoningEffort
                                }
                            >
                                <SelectTrigger
                                    className="w-full"
                                    size="sm"
                                >
                                    <SelectValue placeholder="Default" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem
                                        value={DEFAULT_REASONING_EFFORT_VALUE}
                                    >
                                        Default
                                    </SelectItem>
                                    {availableReasoningEfforts.map((effort) => (
                                        <SelectItem
                                            key={effort}
                                            value={effort}
                                        >
                                            {getReasoningEffortLabel(effort)}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                    ) : undefined
                }
                favoriteModelSet={favoriteModelSet}
                favoriteModels={sortedFavoriteModels}
                groupedModels={groupedModels}
                isSaveDisabled={presetName.trim() === ""}
                modelTarget={modelTarget}
                modelsError={modelsError}
                modelsLoading={modelsLoading}
                onCommandReset={() => {
                    setCommandValue(COMMAND_UNSELECTED_VALUE);
                }}
                onCommandValueChange={setCommandValue}
                onDeletePresetCancel={() => {
                    setDeletePresetOpen(false);
                    setDeletePresetName(undefined);
                }}
                onDeletePresetConfirm={handleDeletePreset}
                onDeletePresetOpenChange={(nextOpen) => {
                    setDeletePresetOpen(nextOpen);
                    if (!nextOpen) {
                        setDeletePresetName(undefined);
                    }
                }}
                onModelTargetChange={setModelTarget}
                onPresetNameChange={setPresetName}
                onPresetSelect={handlePresetSelect}
                onRequestDeletePreset={openDeletePresetDialog}
                onResetCurrentTarget={resetCurrentTarget}
                onSavePreset={handleSavePreset}
                onSelectModel={setModelForTarget}
                onToggleFavorite={toggleFavoriteModel}
                presetName={presetName}
                presetSelectValue={presetSelectValue}
                presets={sortedPresets}
                resetButtonAriaLabel="Reset model to default"
                resetTooltipLabel="Reset to default"
                tabs={MODEL_TARGET_TABS}
            />
        </Dialog>
    ) : undefined;

    return (
        <>
            <Chat
                canSendMessages={canSendMessages}
                composerActionsAccessory={modelActionsAccessory}
                composerValue={draft}
                contentWidthMode="standard"
                hideMessageFooterUntilHover={HIDE_MESSAGE_ACTIONS_UNTIL_HOVER}
                isLoading={isLoading}
                loadingActivity={loadingActivity}
                loadingActivityLog={loadingActivityLog}
                loadingIndicatorComponent={LoadingIndicator}
                loadingIndicatorVariant="ai-elements"
                loadingMessages={[]}
                messages={messages}
                messagesInitialized={messagesInitialized}
                onComposerValueChange={(value) => {
                    setDraft(currentChatId, value);
                }}
                onSendMessage={handleSendMessage}
                overlayComposer
                renderMessageBelowContent={(message: ChatMessage) => {
                    const isOpen = openActivityMessageIds.has(message.id);
                    const activityLog = messageActivityLog.get(message.id);
                    const shouldRender =
                        isOpen &&
                        currentChat !== undefined &&
                        (activityLog !== undefined ||
                            messageActivityLogLoading.has(message.id));

                    return shouldRender ? (
                        <LoadingIndicator
                            activityItems={currentChat.loadingActivity}
                            activityLog={activityLog ?? []}
                            forceOpenReasoning
                            isVisible
                            messages={[]}
                            showEmptyState={false}
                            showHeader={false}
                            variant="ai-elements"
                        />
                    ) : undefined;
                }}
                renderMessageFooter={(message: ChatMessage) => {
                    const internalMessage = messageById.get(message.id);
                    const isErrorMessage =
                        internalMessage !== undefined &&
                        (internalMessage.isError === true ||
                            internalMessage.id.startsWith("error-"));

                    const branchSwitcher =
                        internalMessage === undefined
                            ? undefined
                            : renderBranchSwitcher(
                                  internalMessage.parentId,
                                  internalMessage.id,
                              );

                    const isAssistantMessage =
                        internalMessage?.role === "assistant" &&
                        !isErrorMessage;

                    const showActivity = openActivityMessageIds.has(message.id);

                    const handleToggleActivity = (): void => {
                        setOpenActivityMessageIdsByChat((current) => {
                            const next = new Map(current);
                            const currentSet = next.get(chatActivityKey);
                            const updated = new Set(currentSet);
                            if (updated.has(message.id)) {
                                updated.delete(message.id);
                            } else {
                                updated.add(message.id);
                                const hasActivity = messageActivityLog.has(
                                    message.id,
                                );
                                const isLoading = messageActivityLogLoading.has(
                                    message.id,
                                );
                                if (!hasActivity && !isLoading) {
                                    void loadMessageActivityLog(message.id);
                                }
                            }
                            next.set(chatActivityKey, updated);
                            return next;
                        });
                    };

                    const feedbackControls = isAssistantMessage ? (
                        <MessageFeedback
                            isEligible={isAssistantMessage}
                            messageId={message.id}
                        />
                    ) : undefined;

                    const activityButton = isAssistantMessage ? (
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <Button
                                    aria-label="Toggle assistant activity"
                                    className={
                                        showActivity
                                            ? "bg-primary/10 text-primary hover:bg-primary/15 hover:text-primary rounded-full transition"
                                            : "text-muted-foreground rounded-full transition"
                                    }
                                    onClick={handleToggleActivity}
                                    size="icon-sm"
                                    type="button"
                                    variant="ghost"
                                >
                                    <Activity
                                        aria-hidden="true"
                                        className="size-4"
                                    />
                                </Button>
                            </TooltipTrigger>
                            <TooltipContent>
                                {showActivity
                                    ? "Hide activity"
                                    : "Show activity"}
                            </TooltipContent>
                        </Tooltip>
                    ) : undefined;

                    const editMessage =
                        internalMessage?.role === "user" &&
                        !isErrorMessage &&
                        internalMessage.id !== firstUserMessageId
                            ? internalMessage
                            : undefined;

                    const editButton = editMessage ? (
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <Button
                                    aria-label="Edit"
                                    className="text-muted-foreground rounded-full transition"
                                    disabled={messageActionsDisabled}
                                    onClick={() => {
                                        handleEditMessage(editMessage);
                                    }}
                                    size="icon-sm"
                                    type="button"
                                    variant="ghost"
                                >
                                    <Pencil className="size-3" />
                                    <span className="sr-only">
                                        Edit message
                                    </span>
                                </Button>
                            </TooltipTrigger>
                            <TooltipContent>Edit</TooltipContent>
                        </Tooltip>
                    ) : undefined;

                    const regenerateMessage =
                        internalMessage?.role === "assistant" && !isErrorMessage
                            ? internalMessage
                            : undefined;

                    const regenerateButton = regenerateMessage ? (
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <Button
                                    aria-label="Regenerate response"
                                    className="text-muted-foreground rounded-full transition"
                                    disabled={messageActionsDisabled}
                                    onClick={() => {
                                        handleRegenerateMessage(
                                            regenerateMessage,
                                        );
                                    }}
                                    size="icon-sm"
                                    type="button"
                                    variant="ghost"
                                >
                                    <RefreshCw className="size-3" />
                                    <span className="sr-only">
                                        Regenerate response
                                    </span>
                                </Button>
                            </TooltipTrigger>
                            <TooltipContent>Regenerate</TooltipContent>
                        </Tooltip>
                    ) : undefined;

                    const copyMessage =
                        internalMessage !== undefined && !isErrorMessage
                            ? internalMessage
                            : undefined;

                    const copyButton = copyMessage ? (
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <Button
                                    aria-label="Copy message"
                                    className="text-muted-foreground rounded-full transition"
                                    disabled={messageActionsDisabled}
                                    onClick={() => {
                                        void copyMessageToClipboard(
                                            copyMessage.content,
                                        );
                                    }}
                                    size="icon-sm"
                                    type="button"
                                    variant="ghost"
                                >
                                    <Copy className="size-4" />
                                    <span className="sr-only">Copy</span>
                                </Button>
                            </TooltipTrigger>
                            <TooltipContent>Copy</TooltipContent>
                        </Tooltip>
                    ) : undefined;

                    const traceButton = regenerateMessage ? (
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <Button
                                    aria-label="Trace"
                                    className="text-muted-foreground rounded-full transition"
                                    disabled={messageActionsDisabled}
                                    onClick={() => {
                                        openTracePanel(regenerateMessage.id);
                                    }}
                                    size="icon-sm"
                                    type="button"
                                    variant="ghost"
                                >
                                    <ListTree className="size-4" />
                                    <span className="sr-only">Trace</span>
                                </Button>
                            </TooltipTrigger>
                            <TooltipContent>Show trace</TooltipContent>
                        </Tooltip>
                    ) : undefined;

                    const isUserMessage = internalMessage?.role === "user";
                    const footer =
                        feedbackControls !== undefined ||
                        editButton !== undefined ||
                        regenerateButton !== undefined ||
                        traceButton !== undefined ||
                        copyButton !== undefined ||
                        branchSwitcher !== undefined ? (
                            <div className="flex flex-wrap items-center gap-1">
                                {copyButton}
                                {isUserMessage ? editButton : feedbackControls}
                                {!isUserMessage && regenerateButton}
                                {!isUserMessage && activityButton}
                                {!isUserMessage && traceButton}
                                {branchSwitcher}
                            </div>
                        ) : undefined;

                    return footer;
                }}
                useNativeScrollbar
            />
            <Dialog
                onOpenChange={(nextOpen) => {
                    setEditDialogOpen(nextOpen);
                    if (!nextOpen) {
                        setEditMessageId(undefined);
                        setEditValue("");
                    }
                }}
                open={editDialogOpen}
            >
                <DialogContent className="max-w-2xl">
                    <DialogHeader>
                        <DialogTitle>Edit message</DialogTitle>
                    </DialogHeader>
                    <div className="flex flex-col gap-2">
                        <Textarea
                            onChange={(event) => {
                                setEditValue(event.target.value);
                            }}
                            placeholder="Update your message"
                            rows={6}
                            value={editValue}
                        />
                    </div>
                    <DialogFooter className="gap-2">
                        <Button
                            onClick={() => {
                                setEditDialogOpen(false);
                            }}
                            type="button"
                            variant="ghost"
                        >
                            Cancel
                        </Button>
                        <Button
                            disabled={
                                messageActionsDisabled ||
                                editValue.trim() === ""
                            }
                            onClick={handleEditSave}
                            type="button"
                        >
                            Save
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
            <Sheet
                onOpenChange={(open) => {
                    setTracePanelOpen(open);
                    if (!open) {
                        setTraceMessageId(undefined);
                    }
                }}
                open={tracePanelOpen}
            >
                <SheetContent
                    className="flex !w-[min(100vw,860px)] !max-w-[min(100vw,860px)] flex-col gap-4 p-0"
                    onOpenAutoFocus={(event) => {
                        event.preventDefault();
                    }}
                >
                    <SheetHeader className="border-b px-4 py-4">
                        <div className="flex items-start justify-between gap-4">
                            <div className="space-y-1">
                                <SheetTitle>Chat Turn Trace</SheetTitle>
                                <SheetDescription>
                                    {hasTraceMessageId
                                        ? `Message ${traceMessageId}`
                                        : "Trace detail"}
                                </SheetDescription>
                            </div>
                        </div>
                    </SheetHeader>
                    <div className="min-h-0 flex-1 overflow-hidden">
                        <TraceTurnDebugView
                            detail={traceDetail}
                            error={traceError}
                            loading={traceLoading}
                            summaryOnly
                        />
                    </div>
                </SheetContent>
            </Sheet>
        </>
    );
};
