import { useNavigate, useSearch } from "@tanstack/react-router";
import type { ColumnDef, SortingState } from "@tanstack/react-table";
import { Chat } from "@va/shared/components/chat";
import {
    DEFAULT_HIGHLIGHT_CLASS,
    HighlightedText,
} from "@va/shared/components/highlighted-text";
import { LoadingIndicator } from "@va/shared/components/loading-indicator";
import { Badge } from "@va/shared/components/ui/badge";
import { Button } from "@va/shared/components/ui/button";
import {
    Command,
    CommandEmpty,
    CommandGroup,
    CommandInput,
    CommandItem,
    CommandList,
} from "@va/shared/components/ui/command";
import { Input } from "@va/shared/components/ui/input";
import { Label } from "@va/shared/components/ui/label";
import {
    Popover,
    PopoverContent,
    PopoverTrigger,
} from "@va/shared/components/ui/popover";
import {
    ResizableHandle,
    ResizablePanel,
    ResizablePanelGroup,
} from "@va/shared/components/ui/resizable";
import {
    Sheet,
    SheetContent,
    SheetDescription,
    SheetHeader,
    SheetTitle,
} from "@va/shared/components/ui/sheet";
import { Skeleton } from "@va/shared/components/ui/skeleton";
import { Spinner } from "@va/shared/components/ui/spinner";
import { Switch } from "@va/shared/components/ui/switch";
import {
    ToggleGroup,
    ToggleGroupItem,
} from "@va/shared/components/ui/toggle-group";
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from "@va/shared/components/ui/tooltip";
import { UNIVERSITY_NAME } from "@va/shared/config";
import type { ChatMessage } from "@va/shared/types";
import {
    ChevronLeft,
    ChevronRight,
    ChevronsUpDown,
    Filter,
    ListTree,
    RefreshCw,
    ThumbsDown,
    ThumbsUp,
    UserRound,
} from "lucide-react";
import { type JSX, useCallback, useEffect, useMemo, useState } from "react";

import { DataTable } from "@/components/data-table";

import { useAuth } from "../../auth/contexts/auth-context";
import { useAuthenticatedApi } from "../../auth/hooks/use-authenticated-api";
import { MessageFeedback } from "../../chat/components/message-feedback";
import { useChatStore } from "../../chat/contexts/chat-store-context";
import { ChatStoreProvider } from "../../chat/contexts/chat-store-provider";
import { fetchChatDetail } from "../../chat/lib/api";
import type { ChatDetailResponse, Rating } from "../../chat/types";
import { PageHeader, PageHeaderGroup } from "../../components/page-header";
import { PageSection, PageShell } from "../../components/page-shell";
import { InlineError } from "../../components/page-state";
import { TimeRangeFilter } from "../../components/time-range-filter";
import {
    type CustomTimeRange,
    isTimeRangeValue,
    type TimeRangeValue,
} from "../../lib/time-range";
import { TraceTurnDebugView } from "../../traces/components/trace-turn-debug-view";
import { useTraceDetailByMessage } from "../../traces/hooks/use-trace-detail-by-message";
import { fetchChatListPage, fetchChatUsers } from "../lib/api";
import type {
    ChatListPage as ChatListPageResponse,
    ChatListRow,
    ChatUserOption,
} from "../types";

const formatCost = (cost: number | undefined): string => {
    if (cost === undefined) {
        return "-";
    }
    if (cost === 0) {
        return "$0.00";
    }
    return cost < 0.01 ? `$${cost.toFixed(4)}` : `$${cost.toFixed(2)}`;
};

const formatTimestamp = (value: string): string =>
    new Date(value).toLocaleString("en-US", {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    });

const skeletonLine = (className: string): JSX.Element => (
    <Skeleton className={className} />
);

const chatSkeleton: JSX.Element = (
    <div className="w-full min-w-0 space-y-1">
        {skeletonLine("h-5 w-3/4")}
        {skeletonLine("h-4 w-11/12")}
    </div>
);

const userSkeleton: JSX.Element = (
    <div className="w-full min-w-0">
        {skeletonLine("h-5 w-2/3")}
        {skeletonLine("h-4 w-1/2")}
    </div>
);

const buildColumns = (query: string): ColumnDef<ChatListRow>[] => [
    {
        id: "title",
        accessorKey: "title",
        header: "Chat",
        meta: {
            skeleton: chatSkeleton,
        },
        cell: ({ row }): JSX.Element => {
            const title = row.original.title ?? "Untitled chat";
            const preview = row.original.lastMessagePreview ?? "";

            return (
                <div className="min-w-0 space-y-1">
                    <div className="truncate text-sm font-semibold">
                        <HighlightedText
                            query={query}
                            text={title}
                        />
                    </div>
                    {preview !== "" && (
                        <div className="text-muted-foreground line-clamp-2 text-xs">
                            <HighlightedText
                                query={query}
                                text={preview}
                            />
                        </div>
                    )}
                </div>
            );
        },
    },
    {
        id: "user",
        header: "User",
        meta: {
            skeleton: userSkeleton,
        },
        cell: ({ row }): JSX.Element => {
            const name = row.original.userName ?? "-";
            const email = row.original.userEmail;

            return (
                <div className="min-w-0">
                    <div className="truncate text-sm">{name}</div>
                    {email !== undefined && email !== "" && (
                        <div className="text-muted-foreground truncate text-xs">
                            {email}
                        </div>
                    )}
                </div>
            );
        },
    },
    {
        id: "platform",
        header: "Platform",
        meta: {
            skeleton: skeletonLine("h-6 w-20 rounded-full"),
        },
        cell: ({ row }): JSX.Element => (
            <Badge variant={row.original.isPublic ? "secondary" : "outline"}>
                {row.original.isPublic ? "Public" : "Internal"}
            </Badge>
        ),
    },
    {
        id: "message_count",
        accessorKey: "messageCount",
        header: "Messages",
        enableSorting: true,
        meta: {
            skeleton: skeletonLine("h-4 w-12"),
        },
        cell: ({ row }): JSX.Element => (
            <div className="tabular-nums">
                {row.original.messageCount.toLocaleString()}
            </div>
        ),
    },
    {
        id: "total_cost",
        accessorKey: "totalCost",
        header: "Cost",
        enableSorting: true,
        meta: {
            skeleton: skeletonLine("h-4 w-16"),
        },
        cell: ({ row }): JSX.Element => (
            <div className="tabular-nums">
                {formatCost(row.original.totalCost)}
            </div>
        ),
    },
    {
        id: "feedback_up",
        accessorKey: "feedbackUp",
        header: "Feedback",
        enableSorting: true,
        meta: {
            skeleton: (
                <div className="flex items-center gap-3">
                    {skeletonLine("h-4 w-12")}
                    {skeletonLine("h-4 w-12")}
                </div>
            ),
        },
        cell: ({ row }): JSX.Element => (
            <div className="flex items-center gap-3 text-xs tabular-nums">
                <span className="text-foreground inline-flex items-center gap-1">
                    <ThumbsUp className="size-3" />
                    {row.original.feedbackUp}
                </span>
                <span className="text-muted-foreground inline-flex items-center gap-1">
                    <ThumbsDown className="size-3" />
                    {row.original.feedbackDown}
                </span>
            </div>
        ),
    },
    {
        id: "updated_at",
        accessorKey: "updatedAt",
        header: "Updated",
        enableSorting: true,
        meta: {
            skeleton: skeletonLine("h-3 w-24"),
        },
        cell: ({ row }): JSX.Element => (
            <div className="text-muted-foreground text-xs">
                {formatTimestamp(row.original.updatedAt)}
            </div>
        ),
    },
];

const toChatMessages = (detail: ChatDetailResponse): ChatMessage[] =>
    detail.messages.map((message) => ({
        id: message.id,
        role: message.role,
        content: message.content,
        timestamp: new Date(message.created_at).getTime(),
    }));

const platformOptions = [
    { label: "Both", value: "both" },
    { label: "Internal", value: "internal" },
    { label: "Public", value: "public" },
] as const;

const chatFilterStorageKey = "internal-chat-filters";

interface FeedbackChange {
    previous?: Rating;
    next?: Rating;
}

type PlatformFilter = (typeof platformOptions)[number]["value"];

interface StoredChatFilters {
    platform?: PlatformFilter;
    timeRange?: TimeRangeValue;
    customRange?: {
        start?: string;
        end?: string;
    };
    searchInput?: string;
    selectedUser?: {
        email: string;
        name?: string;
        platform: ChatUserOption["platform"];
    };
}

const isPlatformFilter = (value: string): value is PlatformFilter =>
    platformOptions.some((option) => option.value === value);

const isRecord = (value: unknown): value is Record<string, unknown> =>
    typeof value === "object" && value !== null;

const isChatPlatform = (value: string): value is ChatUserOption["platform"] =>
    value === "internal" || value === "public";

const parseStoredDate = (value?: string): Date | undefined => {
    if (value === undefined || value === "") {
        return undefined;
    }
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? undefined : date;
};

const parseStoredCustomRange = (
    range?: StoredChatFilters["customRange"],
): CustomTimeRange => ({
    start: parseStoredDate(range?.start),
    end: parseStoredDate(range?.end),
});

const parseStoredChatFilters = (
    value: string,
): StoredChatFilters | undefined => {
    try {
        const parsed: unknown = JSON.parse(value);
        if (!isRecord(parsed)) {
            return undefined;
        }
        const customRangeValue = isRecord(parsed.customRange)
            ? parsed.customRange
            : undefined;
        const platformValue =
            typeof parsed.platform === "string" &&
            isPlatformFilter(parsed.platform)
                ? parsed.platform
                : undefined;
        const timeRangeValue =
            typeof parsed.timeRange === "string" &&
            isTimeRangeValue(parsed.timeRange)
                ? parsed.timeRange
                : undefined;
        const selectedUserValue = isRecord(parsed.selectedUser)
            ? parsed.selectedUser
            : undefined;
        const selectedUserEmail =
            typeof selectedUserValue?.email === "string"
                ? selectedUserValue.email
                : undefined;
        const selectedUserPlatform =
            typeof selectedUserValue?.platform === "string" &&
            isChatPlatform(selectedUserValue.platform)
                ? selectedUserValue.platform
                : undefined;
        const hasSelectedUser =
            selectedUserEmail !== undefined &&
            selectedUserEmail !== "" &&
            selectedUserPlatform !== undefined;
        return {
            platform: platformValue,
            timeRange: timeRangeValue,
            searchInput:
                typeof parsed.searchInput === "string"
                    ? parsed.searchInput
                    : undefined,
            customRange: {
                start:
                    typeof customRangeValue?.start === "string"
                        ? customRangeValue.start
                        : undefined,
                end:
                    typeof customRangeValue?.end === "string"
                        ? customRangeValue.end
                        : undefined,
            },
            selectedUser: hasSelectedUser
                ? {
                      email: selectedUserEmail,
                      name:
                          typeof selectedUserValue?.name === "string"
                              ? selectedUserValue.name
                              : undefined,
                      platform: selectedUserPlatform,
                  }
                : undefined,
        };
    } catch {
        return undefined;
    }
};

const getStoredChatFilters = (): StoredChatFilters | undefined => {
    if (typeof window === "undefined") {
        return undefined;
    }
    const stored = window.localStorage.getItem(chatFilterStorageKey);
    if (stored === null || stored === "") {
        return undefined;
    }
    return parseStoredChatFilters(stored);
};

const getStoredSelectedUser = (
    value: StoredChatFilters["selectedUser"] | undefined,
): ChatUserOption | undefined => {
    if (value?.email === undefined || value.email === "") {
        return undefined;
    }
    return {
        email: value.email,
        name: value.name,
        platform: value.platform,
    };
};

const DetailFeedbackInitializer = ({
    detail,
}: {
    detail: ChatDetailResponse;
}): undefined => {
    const initializeMessageFeedback = useChatStore(
        (state) => state.initializeMessageFeedback,
    );

    useEffect(() => {
        initializeMessageFeedback(
            detail.messages.map((message) => ({
                messageId: message.id,
                feedback: message.feedback ?? [],
            })),
        );
    }, [detail, initializeMessageFeedback]);

    return undefined;
};

export const ChatsPage = (): JSX.Element => {
    const api = useAuthenticatedApi();
    const { user } = useAuth();
    const search = useSearch({ from: "/chats" });
    const navigate = useNavigate();
    const storedFilters = useMemo(() => getStoredChatFilters(), []);
    const [searchInput, setSearchInput] = useState(
        storedFilters?.searchInput ?? "",
    );
    const [searchQuery, setSearchQuery] = useState(
        storedFilters?.searchInput?.trim() ?? "",
    );
    const [userSearchInput, setUserSearchInput] = useState("");
    const [userSearchQuery, setUserSearchQuery] = useState("");
    const [userOptions, setUserOptions] = useState<ChatUserOption[]>([]);
    const [userPopoverOpen, setUserPopoverOpen] = useState(false);
    const [userLoading, setUserLoading] = useState(false);
    const [selectedUser, setSelectedUser] = useState<
        ChatUserOption | undefined
    >(() => getStoredSelectedUser(storedFilters?.selectedUser));
    const currentUserOption = useMemo<ChatUserOption | undefined>(
        () =>
            user?.email !== undefined && user.email !== ""
                ? {
                      name: user.name || undefined,
                      email: user.email,
                      platform: "internal",
                  }
                : undefined,
        [user?.email, user?.name],
    );
    const summaryStorageKey = "internal-chat-summary-open";
    const [showSummary, setShowSummary] = useState(() => {
        if (typeof window === "undefined") {
            return true;
        }
        const stored = window.localStorage.getItem(summaryStorageKey);
        return stored === null ? true : stored === "true";
    });
    const [platform, setPlatform] = useState<PlatformFilter>(() => {
        const storedPlatform = storedFilters?.platform;
        if (storedPlatform !== undefined) {
            return storedPlatform;
        }
        return "both";
    });
    const [timeRange, setTimeRange] = useState<TimeRangeValue>(() => {
        const storedTimeRange = storedFilters?.timeRange;
        if (storedTimeRange !== undefined) {
            return storedTimeRange;
        }
        return "30d";
    });
    const [customRange, setCustomRange] = useState<CustomTimeRange>(() =>
        parseStoredCustomRange(storedFilters?.customRange),
    );
    const [pageIndex, setPageIndex] = useState(0);
    const [pageSize, setPageSize] = useState(20);
    const [sorting, setSorting] = useState<SortingState>([
        { id: "updated_at", desc: true },
    ]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | undefined>();
    const [page, setPage] = useState<ChatListPageResponse | undefined>();
    const [refreshToken, setRefreshToken] = useState(0);

    const [sheetOpen, setSheetOpen] = useState(false);
    const [selectedChat, setSelectedChat] = useState<ChatListRow | undefined>();
    const [detail, setDetail] = useState<ChatDetailResponse | undefined>();
    const [detailLoading, setDetailLoading] = useState(false);
    const [detailError, setDetailError] = useState<string | undefined>();
    const [tracePanelOpen, setTracePanelOpen] = useState(false);
    const [traceMessageId, setTraceMessageId] = useState<string | undefined>();

    const {
        detail: traceDetail,
        loading: traceLoading,
        error: traceError,
        refresh: refreshTrace,
    } = useTraceDetailByMessage(traceMessageId);

    const applyFeedbackChange = useCallback(
        (change: FeedbackChange): void => {
            if (!selectedChat) {
                return;
            }

            const deltaUp =
                (change.previous === "thumbsUp" ? -1 : 0) +
                (change.next === "thumbsUp" ? 1 : 0);
            const deltaDown =
                (change.previous === "thumbsDown" ? -1 : 0) +
                (change.next === "thumbsDown" ? 1 : 0);

            if (deltaUp === 0 && deltaDown === 0) {
                return;
            }

            setPage((prev) => {
                if (!prev) {
                    return prev;
                }

                return {
                    ...prev,
                    items: prev.items.map((item) => {
                        if (item.id !== selectedChat.id) {
                            return item;
                        }
                        return {
                            ...item,
                            feedbackUp: Math.max(0, item.feedbackUp + deltaUp),
                            feedbackDown: Math.max(
                                0,
                                item.feedbackDown + deltaDown,
                            ),
                        };
                    }),
                };
            });

            setSelectedChat((prev) => {
                if (prev?.id !== selectedChat.id) {
                    return prev;
                }
                return {
                    ...prev,
                    feedbackUp: Math.max(0, prev.feedbackUp + deltaUp),
                    feedbackDown: Math.max(0, prev.feedbackDown + deltaDown),
                };
            });
        },
        [selectedChat],
    );

    useEffect((): (() => void) => {
        const timeout = setTimeout(() => {
            setSearchQuery(searchInput.trim());
            setPageIndex(0);
        }, 300);

        return (): void => {
            clearTimeout(timeout);
        };
    }, [searchInput]);

    useEffect(() => {
        if (typeof window === "undefined") {
            return;
        }
        window.localStorage.setItem(
            summaryStorageKey,
            showSummary ? "true" : "false",
        );
    }, [showSummary, summaryStorageKey]);

    useEffect(() => {
        if (typeof window === "undefined") {
            return;
        }
        const payload: StoredChatFilters = {
            platform,
            timeRange,
            customRange: {
                start: customRange.start?.toISOString(),
                end: customRange.end?.toISOString(),
            },
            searchInput,
            selectedUser: selectedUser
                ? {
                      email: selectedUser.email,
                      name: selectedUser.name,
                      platform: selectedUser.platform,
                  }
                : undefined,
        };
        window.localStorage.setItem(
            chatFilterStorageKey,
            JSON.stringify(payload),
        );
    }, [customRange, platform, searchInput, selectedUser, timeRange]);

    useEffect((): (() => void) => {
        const timeout = setTimeout(() => {
            setUserSearchQuery(userSearchInput.trim());
        }, 300);

        return (): void => {
            clearTimeout(timeout);
        };
    }, [userSearchInput]);

    useEffect(() => {
        setPageIndex(0);
    }, [
        customRange,
        platform,
        pageSize,
        sorting,
        timeRange,
        selectedUser?.email,
    ]);

    useEffect((): (() => void) => {
        let isMounted = true;

        const loadUsers = async (): Promise<void> => {
            if (!userPopoverOpen) {
                return;
            }

            setUserLoading(true);
            try {
                const response = await fetchChatUsers(api, {
                    platform: platform === "both" ? undefined : platform,
                    search: userSearchQuery,
                    limit: 50,
                });

                if (!isMounted) {
                    return;
                }

                setUserOptions(response);
            } catch {
                if (!isMounted) {
                    return;
                }
                setUserOptions([]);
            } finally {
                if (isMounted) {
                    setUserLoading(false);
                }
            }
        };

        void loadUsers();

        return (): void => {
            isMounted = false;
        };
    }, [api, platform, userPopoverOpen, userSearchQuery]);

    useEffect((): (() => void) => {
        let isMounted = true;

        const load = async (): Promise<void> => {
            setLoading(true);
            setError(undefined);
            try {
                const sortKey = sorting[0]?.id ?? "updated_at";
                const descending = sorting[0]?.desc ?? true;

                const response = await fetchChatListPage(api, {
                    platform: platform === "both" ? undefined : platform,
                    search: searchQuery,
                    userEmail: selectedUser?.email,
                    limit: pageSize,
                    offset: pageIndex * pageSize,
                    sortBy: sortKey,
                    descending,
                    timeRange,
                    customRange,
                });

                // TODO: Remove this artificial delay (for testing skeleton loading)
                // await new Promise((resolve) => {
                //     setTimeout(resolve, 1500);
                // });

                if (!isMounted) {
                    return;
                }

                setPage(response);
            } catch (error_) {
                if (!isMounted) {
                    return;
                }
                setError(
                    error_ instanceof Error
                        ? error_.message
                        : "Failed to load chats",
                );
            } finally {
                if (isMounted) {
                    setLoading(false);
                }
            }
        };

        void load();

        return (): void => {
            isMounted = false;
        };
    }, [
        api,
        customRange,
        pageIndex,
        pageSize,
        platform,
        searchQuery,
        selectedUser?.email,
        sorting,
        refreshToken,
        timeRange,
    ]);

    const selectedChatId = selectedChat?.id;

    useEffect((): (() => void) | undefined => {
        if (!sheetOpen || selectedChatId === undefined) {
            return undefined;
        }

        let isMounted = true;

        const loadDetail = async (): Promise<void> => {
            setDetailLoading(true);
            setDetailError(undefined);
            try {
                const response = await fetchChatDetail(api, selectedChatId);
                if (!isMounted) {
                    return;
                }
                setDetail(response);
            } catch (error_) {
                if (!isMounted) {
                    return;
                }
                setDetailError(
                    error_ instanceof Error
                        ? error_.message
                        : "Failed to load chat",
                );
            } finally {
                if (isMounted) {
                    setDetailLoading(false);
                }
            }
        };

        void loadDetail();

        return (): void => {
            isMounted = false;
        };
    }, [api, selectedChatId, sheetOpen]);

    const highlightQuery = searchInput.trim();
    const columns = useMemo(
        () => buildColumns(highlightQuery),
        [highlightQuery],
    );

    const tableData = useMemo(() => page?.items ?? [], [page]);
    const pageCount = Math.max(1, Math.ceil((page?.total ?? 0) / pageSize));

    const selectedUserLabel =
        selectedUser?.name ?? selectedUser?.email ?? "All users";

    const orderedUserOptions = useMemo(() => {
        if (platform === "public" || !currentUserOption) {
            return userOptions;
        }

        const currentIndex = userOptions.findIndex(
            (option) =>
                option.email === currentUserOption.email &&
                option.platform === currentUserOption.platform,
        );

        if (currentIndex === -1) {
            return userSearchInput.trim() === ""
                ? [currentUserOption, ...userOptions]
                : userOptions;
        }

        const filtered = userOptions.filter(
            (option) =>
                option.email !== currentUserOption.email ||
                option.platform !== currentUserOption.platform,
        );

        return [currentUserOption, ...filtered];
    }, [currentUserOption, platform, userOptions, userSearchInput]);

    const messages = useMemo(
        (): ChatMessage[] => (detail ? toChatMessages(detail) : []),
        [detail],
    );

    const detailPlatformLabel =
        selectedChat?.isPublic === true ? "Public" : "Internal";
    const detailTitle = selectedChat?.title ?? "Untitled chat";
    const detailUpdatedAt = selectedChat?.updatedAt;
    const hasTraceMessageId =
        traceMessageId !== undefined && traceMessageId.trim() !== "";

    useEffect(() => {
        const baseTitle = `${UNIVERSITY_NAME} Enrollment Agent`;
        document.title = selectedChat
            ? `${detailTitle} · Chats · ${baseTitle}`
            : `Chats · ${baseTitle}`;
    }, [detailTitle, selectedChat]);
    const selectedIndex = selectedChat
        ? tableData.findIndex((row) => row.id === selectedChat.id)
        : -1;
    const canGoPrev = selectedIndex > 0;
    const canGoNext =
        selectedIndex >= 0 && selectedIndex < tableData.length - 1;

    const openChat = (chat: ChatListRow): void => {
        setSelectedChat(chat);
        setDetail(undefined);
        setDetailError(undefined);
        setDetailLoading(true);
        setSheetOpen(true);
    };

    const openTracePanel = (messageId: string): void => {
        setTraceMessageId(messageId);
        setTracePanelOpen(true);
    };

    useEffect(() => {
        if (search.chat === undefined) {
            if (sheetOpen) {
                setSheetOpen(false);
            }
            setSelectedChat(undefined);
            return;
        }

        if (selectedChat?.id === search.chat) {
            if (!sheetOpen) {
                setSheetOpen(true);
            }
            return;
        }

        const match = tableData.find((row) => row.id === search.chat);
        if (match) {
            openChat(match);
        } else {
            setSelectedChat(undefined);
            setSheetOpen(false);
        }
    }, [search.chat, selectedChat, sheetOpen, tableData]);

    let detailContent: JSX.Element = (
        <div className="text-muted-foreground flex h-full items-center justify-center text-sm">
            Select a chat to view.
        </div>
    );
    if (detailLoading) {
        detailContent = (
            <div className="text-muted-foreground flex h-full items-center justify-center gap-2">
                <Spinner className="size-4" />
                Loading...
            </div>
        );
    } else if (detailError !== undefined) {
        detailContent = (
            <div className="text-destructive flex h-full items-center justify-center px-6 text-center text-sm">
                {detailError}
            </div>
        );
    } else if (detail !== undefined) {
        const chatPanel = (
            <ChatStoreProvider>
                <DetailFeedbackInitializer detail={detail} />
                <Chat
                    autoScroll={false}
                    canSendMessages={false}
                    contentWidthMode="standard"
                    disableVoiceFeatures
                    highlightQuery={highlightQuery}
                    isLoading={false}
                    loadingIndicatorComponent={LoadingIndicator}
                    messages={messages}
                    messagesInitialized
                    onSendMessage={(): void => undefined}
                    renderMessageFooter={(message) => (
                        <div className="flex items-center gap-2">
                            <MessageFeedback
                                isEligible={
                                    message.role === "assistant" &&
                                    !message.id.startsWith("error-")
                                }
                                messageId={message.id}
                                onFeedbackChange={applyFeedbackChange}
                            />
                            {message.role === "assistant" &&
                            !message.id.startsWith("error-") ? (
                                <TooltipProvider delayDuration={0}>
                                    <Tooltip>
                                        <TooltipTrigger asChild>
                                            <Button
                                                aria-label="Trace"
                                                className="rounded-full"
                                                onClick={() => {
                                                    openTracePanel(message.id);
                                                }}
                                                size="icon-sm"
                                                type="button"
                                                variant="ghost"
                                            >
                                                <ListTree className="size-4" />
                                            </Button>
                                        </TooltipTrigger>
                                        <TooltipContent>Trace</TooltipContent>
                                    </Tooltip>
                                </TooltipProvider>
                            ) : undefined}
                        </div>
                    )}
                    useNativeScrollbar
                />
            </ChatStoreProvider>
        );

        detailContent = showSummary ? (
            <ResizablePanelGroup
                className="min-h-0 flex-1"
                direction="vertical"
            >
                <ResizablePanel
                    className="min-h-0"
                    defaultSize={30}
                    maxSize={60}
                    minSize={20}
                >
                    <div className="flex h-full min-h-0 flex-col border-b pr-0 pl-4">
                        <div className="min-h-0 flex-1 overflow-auto text-sm leading-relaxed whitespace-pre-line">
                            {detail.summary ?? (
                                <span className="text-muted-foreground">
                                    Summary will appear once generated for this
                                    chat.
                                </span>
                            )}
                        </div>
                    </div>
                </ResizablePanel>
                <ResizableHandle withHandle />
                <ResizablePanel
                    className="min-h-0"
                    minSize={40}
                >
                    <div className="h-full min-h-0 overflow-hidden">
                        {chatPanel}
                    </div>
                </ResizablePanel>
            </ResizablePanelGroup>
        ) : (
            <div className="h-full min-h-0 overflow-hidden">{chatPanel}</div>
        );
    }

    return (
        <PageShell
            className="overflow-hidden"
            variant="dashboard"
        >
            <PageHeader title="Chats">
                <PageHeaderGroup label="Platform">
                    <ToggleGroup
                        onValueChange={(value) => {
                            const next = isPlatformFilter(value)
                                ? value
                                : "both";
                            setPlatform(next);
                        }}
                        size="sm"
                        type="single"
                        value={platform}
                        variant="outline"
                    >
                        {platformOptions.map((option) => (
                            <ToggleGroupItem
                                key={option.value}
                                value={option.value}
                            >
                                {option.label}
                            </ToggleGroupItem>
                        ))}
                    </ToggleGroup>
                </PageHeaderGroup>
                <PageHeaderGroup>
                    <Popover
                        onOpenChange={(open) => {
                            setUserPopoverOpen(open);
                            if (open) {
                                setUserSearchInput("");
                                setUserSearchQuery("");
                            }
                        }}
                        open={userPopoverOpen}
                    >
                        <PopoverTrigger asChild>
                            <Button
                                className="h-8 w-[240px] justify-between gap-2"
                                size="sm"
                                variant="outline"
                            >
                                <span className="flex min-w-0 items-center gap-2">
                                    <UserRound className="text-muted-foreground size-4" />
                                    <span className="truncate">
                                        {selectedUserLabel}
                                    </span>
                                </span>
                                <ChevronsUpDown className="text-muted-foreground size-4" />
                            </Button>
                        </PopoverTrigger>
                        <PopoverContent
                            align="start"
                            className="w-[320px] p-0"
                        >
                            <Command shouldFilter={false}>
                                <CommandInput
                                    onValueChange={setUserSearchInput}
                                    placeholder="Search users..."
                                    value={userSearchInput}
                                />
                                <CommandList>
                                    <CommandEmpty>
                                        {userLoading
                                            ? "Loading users..."
                                            : "No users found"}
                                    </CommandEmpty>
                                    <CommandGroup>
                                        {userSearchInput === "" && (
                                            <CommandItem
                                                onSelect={() => {
                                                    setSelectedUser(undefined);
                                                    setUserPopoverOpen(false);
                                                }}
                                            >
                                                All users
                                            </CommandItem>
                                        )}
                                        {orderedUserOptions.map((user) => (
                                            <CommandItem
                                                key={`${user.platform}-${user.email}`}
                                                onSelect={() => {
                                                    setSelectedUser(user);
                                                    setUserPopoverOpen(false);
                                                }}
                                                value={user.email}
                                            >
                                                <div className="flex min-w-0 flex-1 flex-col">
                                                    <span className="truncate text-sm">
                                                        {user.name ??
                                                            user.email}
                                                    </span>
                                                    {user.name !== undefined &&
                                                        user.name !== "" && (
                                                            <span className="text-muted-foreground truncate text-xs">
                                                                {user.email}
                                                            </span>
                                                        )}
                                                </div>
                                                <Badge
                                                    variant={
                                                        user.platform ===
                                                        "public"
                                                            ? "secondary"
                                                            : "outline"
                                                    }
                                                >
                                                    {user.platform === "public"
                                                        ? "Public"
                                                        : "Internal"}
                                                </Badge>
                                            </CommandItem>
                                        ))}
                                    </CommandGroup>
                                </CommandList>
                            </Command>
                        </PopoverContent>
                    </Popover>
                </PageHeaderGroup>
                <PageHeaderGroup>
                    <TimeRangeFilter
                        customRange={customRange}
                        onChange={setTimeRange}
                        onCustomRangeChange={setCustomRange}
                        value={timeRange}
                    />
                </PageHeaderGroup>
                <PageHeaderGroup>
                    <Input
                        className="h-8 w-[240px]"
                        onChange={(event) => {
                            setSearchInput(event.target.value);
                        }}
                        placeholder="Search by message or title"
                        value={searchInput}
                    />
                    <Button
                        onClick={() => {
                            setSearchInput("");
                            setSearchQuery("");
                            setUserSearchInput("");
                            setUserSearchQuery("");
                            setSelectedUser(undefined);
                            setPlatform("both");
                            setTimeRange("30d");
                            setCustomRange({});
                            setPageIndex(0);
                        }}
                        size="sm"
                        variant="outline"
                    >
                        <Filter className="mr-2 size-4" />
                        Clear
                    </Button>
                </PageHeaderGroup>
                <Button
                    onClick={() => {
                        setPageIndex(0);
                        setSearchQuery(searchInput.trim());
                        setRefreshToken((value) => value + 1);
                    }}
                    size="sm"
                    variant="outline"
                >
                    <RefreshCw className="mr-2 size-4" />
                    Refresh
                </Button>
            </PageHeader>

            <PageSection className="flex min-h-0 flex-1 flex-col">
                {error !== undefined && <InlineError message={error} />}

                <DataTable
                    columns={columns}
                    data={tableData}
                    emptyMessage="No chats match your filters"
                    isLoading={loading}
                    isRowSelected={(row) => row.id === selectedChat?.id}
                    manualPagination
                    manualSorting
                    onPaginationChange={(updater) => {
                        if (typeof updater === "function") {
                            const next = updater({
                                pageIndex,
                                pageSize,
                            });
                            setPageIndex(next.pageIndex);
                            setPageSize(next.pageSize);
                        } else {
                            setPageIndex(updater.pageIndex);
                            setPageSize(updater.pageSize);
                        }
                    }}
                    onRowClick={(chat) => {
                        openChat(chat);
                        void navigate({
                            search: (prev) => ({
                                ...prev,
                                chat: chat.id,
                            }),
                            to: "/chats",
                        });
                    }}
                    onSortingChange={setSorting}
                    pageCount={pageCount}
                    pagination={{ pageIndex, pageSize }}
                    sorting={sorting}
                />
            </PageSection>

            <Sheet
                onOpenChange={(open) => {
                    setSheetOpen(open);
                    if (!open) {
                        setDetail(undefined);
                        setDetailError(undefined);
                        setSelectedChat(undefined);
                        setTracePanelOpen(false);
                        setTraceMessageId(undefined);
                        void navigate({
                            search: (prev) => ({
                                ...prev,
                                chat: undefined,
                            }),
                            to: "/chats",
                        });
                    }
                }}
                open={sheetOpen}
            >
                <SheetContent
                    className="flex !w-[min(100vw,860px)] !max-w-[min(100vw,860px)] flex-col gap-4 p-0"
                    onOpenAutoFocus={(event) => {
                        event.preventDefault();
                    }}
                >
                    <SheetHeader className="border-b px-4 py-4">
                        <div className="flex items-start justify-between gap-4">
                            <SheetTitle>{detailTitle}</SheetTitle>
                            <div className="flex items-center gap-4">
                                <div className="flex items-center gap-2">
                                    <Label
                                        className="text-muted-foreground text-xs"
                                        htmlFor="summary-toggle"
                                    >
                                        Summary
                                    </Label>
                                    <Switch
                                        checked={showSummary}
                                        id="summary-toggle"
                                        onCheckedChange={setShowSummary}
                                    />
                                </div>
                                <TooltipProvider>
                                    <div className="mr-8 flex items-center gap-2">
                                        <Tooltip>
                                            <TooltipTrigger asChild>
                                                <Button
                                                    aria-label="Previous chat"
                                                    disabled={!canGoPrev}
                                                    onClick={() => {
                                                        if (!canGoPrev) {
                                                            return;
                                                        }
                                                        const previous =
                                                            tableData[
                                                                selectedIndex -
                                                                    1
                                                            ];
                                                        openChat(previous);
                                                        void navigate({
                                                            search: (prev) => ({
                                                                ...prev,
                                                                chat: previous.id,
                                                            }),
                                                            to: "/chats",
                                                        });
                                                    }}
                                                    size="icon-sm"
                                                    variant="outline"
                                                >
                                                    <ChevronLeft className="size-4" />
                                                </Button>
                                            </TooltipTrigger>
                                            <TooltipContent>
                                                Previous Chat
                                            </TooltipContent>
                                        </Tooltip>
                                        <Tooltip>
                                            <TooltipTrigger asChild>
                                                <Button
                                                    aria-label="Next chat"
                                                    disabled={!canGoNext}
                                                    onClick={() => {
                                                        if (!canGoNext) {
                                                            return;
                                                        }
                                                        const next =
                                                            tableData[
                                                                selectedIndex +
                                                                    1
                                                            ];
                                                        openChat(next);
                                                        void navigate({
                                                            search: (prev) => ({
                                                                ...prev,
                                                                chat: next.id,
                                                            }),
                                                            to: "/chats",
                                                        });
                                                    }}
                                                    size="icon-sm"
                                                    variant="outline"
                                                >
                                                    <ChevronRight className="size-4" />
                                                </Button>
                                            </TooltipTrigger>
                                            <TooltipContent>
                                                Next Chat
                                            </TooltipContent>
                                        </Tooltip>
                                    </div>
                                </TooltipProvider>
                            </div>
                        </div>
                        <SheetDescription>
                            {selectedChat !== undefined &&
                            detailUpdatedAt !== undefined ? (
                                <span className="inline-flex flex-wrap items-center gap-2">
                                    <Badge
                                        variant={
                                            selectedChat.isPublic
                                                ? "secondary"
                                                : "outline"
                                        }
                                    >
                                        {detailPlatformLabel}
                                    </Badge>
                                    <span>
                                        Updated{" "}
                                        {formatTimestamp(detailUpdatedAt)}
                                    </span>
                                </span>
                            ) : (
                                "Chat details"
                            )}
                        </SheetDescription>
                    </SheetHeader>

                    <div className="min-h-0 flex-1 overflow-hidden">
                        {detailContent}
                    </div>

                    {highlightQuery !== "" && (
                        <div className="border-t px-4 py-3">
                            <div className="text-muted-foreground text-xs">
                                Highlighting matches for{" "}
                                <span className={DEFAULT_HIGHLIGHT_CLASS}>
                                    {highlightQuery}
                                </span>
                            </div>
                        </div>
                    )}
                </SheetContent>
            </Sheet>

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
                            <Button
                                onClick={() => {
                                    void refreshTrace();
                                }}
                                size="sm"
                                type="button"
                                variant="outline"
                            >
                                <RefreshCw className="mr-2 size-4" />
                                Refresh
                            </Button>
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
        </PageShell>
    );
};
