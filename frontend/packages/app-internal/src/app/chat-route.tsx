import type { JSX } from "react";

import { AuthPage } from "../auth/components/auth-page";
import { useAuth } from "../auth/contexts/auth-context";
import { ChatPage } from "../chat/components/chat-page";

export const ChatRoute = (): JSX.Element | null => {
    const { user } = useAuth();
    if (!user) {
        return <AuthPage />;
    }
    return <ChatPage />;
};
