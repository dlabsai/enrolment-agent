import { type JSX, type ReactNode, useMemo } from "react";

import { useAuthenticatedApi } from "../../auth/hooks/use-authenticated-api";
import { createChatStore } from "../lib/store";
import { ChatStoreContext } from "./chat-store-context";

interface ChatStoreProviderProps {
    children: ReactNode;
}

export const ChatStoreProvider = ({
    children,
}: ChatStoreProviderProps): JSX.Element => {
    const api = useAuthenticatedApi();

    const store = useMemo(() => createChatStore(api), [api]);

    return <ChatStoreContext value={store}>{children}</ChatStoreContext>;
};
