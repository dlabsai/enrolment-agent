import { useNavigate, useSearch } from "@tanstack/react-router";
import {
    Sheet,
    SheetContent,
    SheetTrigger,
} from "@va/shared/components/ui/sheet";
import { useSidebar } from "@va/shared/components/ui/sidebar";
import { UNIVERSITY_NAME } from "@va/shared/config";
import { useIsMobile } from "@va/shared/hooks/use-is-mobile";
import { Menu, PanelLeft, SquarePen } from "lucide-react";
import { type JSX, useEffect, useRef, useState } from "react";

import { useChatActions, useChatStore } from "../contexts/chat-store-context";
import { ChatStoreProvider } from "../contexts/chat-store-provider";
import { ChatArea } from "./chat-area";
import { ChatList } from "./chat-list";

const MobileChatSheet = (): JSX.Element => {
    const [open, setOpen] = useState(false);

    return (
        <Sheet
            onOpenChange={setOpen}
            open={open}
        >
            <SheetTrigger asChild>
                <button
                    className="text-foreground hover:bg-accent hover:text-accent-foreground flex size-9 items-center justify-center rounded-full transition-colors"
                    type="button"
                >
                    <Menu className="size-4" />
                    <span className="sr-only">Open chats</span>
                </button>
            </SheetTrigger>
            <SheetContent
                className="w-64! max-w-none! overflow-x-hidden p-0"
                side="left"
            >
                <ChatList
                    className="h-full w-full border-r-0"
                    onRequestClose={() => {
                        setOpen(false);
                    }}
                />
            </SheetContent>
        </Sheet>
    );
};

const ChatPageContent = (): JSX.Element => {
    const chatsLoaded = useChatStore((state) => state.chatsLoaded);
    const currentChatId = useChatStore((state) => state.currentChatId);
    const currentChatTitle = useChatStore((state) =>
        state.currentChatId === undefined
            ? undefined
            : state.chats.get(state.currentChatId)?.title,
    );

    const search = useSearch({ from: "/chat" });
    const navigate = useNavigate({ from: "/chat" });

    const { loadChats, selectChat, clearCurrentChat } = useChatActions();
    const { toggleSidebar } = useSidebar();
    const isMobile = useIsMobile();

    useEffect((): void => {
        if (!chatsLoaded) {
            void loadChats();
        }
    }, [chatsLoaded, loadChats]);

    useEffect(() => {
        const baseTitle = `${UNIVERSITY_NAME} Enrollment Agent`;
        const chatTitle = currentChatTitle ?? "Untitled chat";
        document.title =
            currentChatId === undefined
                ? `Chat · ${baseTitle}`
                : `${chatTitle} · Chat · ${baseTitle}`;
    }, [currentChatId, currentChatTitle]);

    const syncFromUrlRef = useRef(false);
    const lastSearchRef = useRef(search.chat);

    useEffect(() => {
        if (lastSearchRef.current === search.chat) {
            return;
        }
        lastSearchRef.current = search.chat;
        syncFromUrlRef.current = true;
        if (search.chat === undefined) {
            clearCurrentChat();
            return;
        }
        void selectChat(search.chat);
    }, [clearCurrentChat, search.chat, selectChat]);

    useEffect(() => {
        if (syncFromUrlRef.current) {
            if (currentChatId === search.chat) {
                syncFromUrlRef.current = false;
            }
            return;
        }
        if (currentChatId === search.chat) {
            return;
        }
        void navigate({
            search: () => ({
                chat: currentChatId,
                platform: undefined,
                userId: undefined,
                userEmail: undefined,
            }),
            to: "/chat",
        });
    }, [currentChatId, navigate, search.chat]);

    const canSendMessages = true;

    const handleNewChat = (): void => {
        clearCurrentChat();
    };

    return (
        <div className="flex h-full min-h-0 min-w-0 flex-1 overflow-hidden">
            <ChatList className="hidden md:flex" />

            <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
                <div className="flex items-center justify-between gap-2 px-3 py-2 md:hidden">
                    <div className="flex items-center gap-1">
                        <button
                            className="text-foreground hover:bg-accent hover:text-accent-foreground flex size-9 items-center justify-center rounded-full transition-colors"
                            onClick={toggleSidebar}
                            type="button"
                        >
                            <PanelLeft className="size-4" />
                            <span className="sr-only">Open sidebar</span>
                        </button>
                        {isMobile && <MobileChatSheet />}
                    </div>
                    <div className="flex items-center gap-1">
                        <button
                            className="text-foreground hover:bg-accent hover:text-accent-foreground flex size-9 items-center justify-center rounded-full transition-colors"
                            onClick={handleNewChat}
                            type="button"
                        >
                            <SquarePen className="size-4" />
                            <span className="sr-only">New chat</span>
                        </button>
                    </div>
                </div>

                <div className="min-h-0 flex-1">
                    <ChatArea canSendMessages={canSendMessages} />
                </div>
            </div>
        </div>
    );
};

export const ChatPage = (): JSX.Element => (
    <ChatStoreProvider>
        <ChatPageContent />
    </ChatStoreProvider>
);
