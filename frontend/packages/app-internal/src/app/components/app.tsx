import { Outlet, useLocation, useNavigate } from "@tanstack/react-router";
import {
    SidebarInset,
    SidebarProvider,
} from "@va/shared/components/ui/sidebar";
import { Toaster } from "@va/shared/components/ui/sonner";
import { UNIVERSITY_NAME } from "@va/shared/config";
import { logger } from "@va/shared/lib/logger";
import { type JSX, useEffect, useMemo, useState } from "react";
import { ErrorBoundary, type FallbackProps } from "react-error-boundary";

import { AuthPage } from "../../auth/components/auth-page";
import { useAuth } from "../../auth/contexts/auth-context";
import { AuthProvider } from "../../auth/contexts/auth-provider";
import { PageError, PageLoading } from "../../components/page-state";
import { ThemeProvider } from "../../lib/theme-provider";
import { AppSidebar, type AppView } from "./app-sidebar";

const appViewLookup: Record<AppView, true> = {
    chat: true,
    chats: true,
    usage: true,
    traces: true,
    analytics: true,
    "public-analytics": true,
    evals: true,
    instructions: true,
    settings: true,
};

const appViewTitle: Record<AppView, string> = {
    chat: "Chat",
    chats: "Chats",
    usage: "Usage",
    traces: "Traces",
    analytics: "Chat Analytics",
    "public-analytics": "Public Analytics",
    evals: "Evals",
    instructions: "Instructions",
    settings: "Settings",
};

const isAppView = (value: string): value is AppView =>
    Object.hasOwn(appViewLookup, value);

const resolveView = (pathname: string, isAdmin: boolean): AppView => {
    const normalized = pathname.replace(/^\/+/u, "");
    const resolved = normalized === "" ? "chat" : normalized;
    if (resolved.startsWith("traces/")) {
        return "traces";
    }
    if (!isAppView(resolved)) {
        return "chat";
    }
    if (!isAdmin && resolved !== "chat") {
        return "chat";
    }
    return resolved;
};

const AppErrorFallback = ({
    error,
    resetErrorBoundary,
}: FallbackProps): JSX.Element => (
    <PageError
        className="h-screen"
        message={
            error instanceof Error && error.message !== ""
                ? error.message
                : "An unexpected error occurred."
        }
        onRetry={resetErrorBoundary}
    />
);

const AppContent = (): JSX.Element => {
    const { loading: authLoading, user, logout } = useAuth();
    const [sidebarOpen, setSidebarOpen] = useState(
        () => window.localStorage.getItem("internal-sidebar-open") === "true",
    );
    const isAdmin = user?.role === "admin" || user?.role === "dev";
    const navigate = useNavigate();
    const { pathname } = useLocation();

    const activeView = useMemo(
        () => resolveView(pathname, isAdmin),
        [isAdmin, pathname],
    );

    useEffect(() => {
        const baseTitle = `${UNIVERSITY_NAME} Enrollment Agent`;
        if (!user) {
            document.title = baseTitle;
            return;
        }
        const viewTitle = appViewTitle[activeView];
        document.title = `${viewTitle} · ${baseTitle}`;
    }, [activeView, user]);

    useEffect(() => {
        if (!user) {
            return;
        }
        if (!isAdmin && activeView !== "chat") {
            void navigate({
                replace: true,
                search: {
                    chat: undefined,
                    platform: undefined,
                    userId: undefined,
                    userEmail: undefined,
                },
                to: "/chat",
            });
        }
    }, [activeView, isAdmin, navigate, user]);

    const content = authLoading ? (
        <PageLoading className="h-screen" />
    ) : user ? (
        <SidebarProvider
            className="h-svh min-h-0 overflow-hidden"
            onOpenChange={(open) => {
                setSidebarOpen(open);
                window.localStorage.setItem(
                    "internal-sidebar-open",
                    String(open),
                );
            }}
            open={sidebarOpen}
        >
            <AppSidebar
                activeView={activeView}
                isAdmin={isAdmin}
                onLogout={logout}
                onViewChange={(view) => {
                    void navigate({ to: `/${view}` });
                }}
                user={user}
            />
            <SidebarInset className="min-h-0 overflow-hidden">
                <div className="flex min-h-0 flex-1 overflow-hidden">
                    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
                        <Outlet />
                    </div>
                </div>
            </SidebarInset>
        </SidebarProvider>
    ) : (
        <AuthPage />
    );

    return (
        <div className="h-screen min-h-screen overflow-hidden font-sans">
            {content}
        </div>
    );
};

export const App = (): JSX.Element => (
    <ThemeProvider>
        <AuthProvider>
            <ErrorBoundary
                FallbackComponent={AppErrorFallback}
                onError={(error, info) => {
                    logger.error("Internal app crashed:", error, info);
                }}
            >
                <AppContent />
            </ErrorBoundary>
            <Toaster />
        </AuthProvider>
    </ThemeProvider>
);
