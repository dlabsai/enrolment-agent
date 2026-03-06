import {
    createHashHistory,
    createRootRoute,
    createRoute,
    createRouter,
    redirect,
} from "@tanstack/react-router";

import { AnalyticsPage } from "../chat-analytics/components/analytics-page";
import { ChatsPage } from "../chats/components/chats-page";
import { EvalsPage } from "../evals/components/evals-page";
import { InstructionsPage } from "../instructions/components/instructions-page";
import { PublicAnalyticsPage } from "../public-analytics/components/public-analytics-page";
import { SettingsPage } from "../settings/components/settings-page";
import { TraceDetailPage } from "../traces/components/trace-detail-page";
import { TracesPage } from "../traces/components/traces-page";
import { UsagePage } from "../usage/components/usage-page";
import { ChatRoute } from "./chat-route";
import { App } from "./components/app";

const RootRoute = createRootRoute({
    component: App,
});

const IndexRoute = createRoute({
    getParentRoute: () => RootRoute,
    path: "/",
    beforeLoad: () =>
        redirect({
            to: "/chat",
            search: {
                chat: undefined,
                platform: undefined,
                userId: undefined,
                userEmail: undefined,
            },
        }),
});

const ChatRouteEntry = createRoute({
    getParentRoute: () => RootRoute,
    path: "/chat",
    validateSearch: (search) => ({
        chat: typeof search.chat === "string" ? search.chat : undefined,
        platform:
            search.platform === "my" ||
            search.platform === "internal" ||
            search.platform === "public"
                ? search.platform
                : undefined,
        userId: typeof search.userId === "string" ? search.userId : undefined,
        userEmail:
            typeof search.userEmail === "string" ? search.userEmail : undefined,
    }),
    component: ChatRoute,
});

const ChatsRoute = createRoute({
    getParentRoute: () => RootRoute,
    path: "/chats",
    validateSearch: (search) => ({
        chat: typeof search.chat === "string" ? search.chat : undefined,
    }),
    component: ChatsPage,
});

const UsageRoute = createRoute({
    getParentRoute: () => RootRoute,
    path: "/usage",
    component: UsagePage,
});

const TracesRoute = createRoute({
    getParentRoute: () => RootRoute,
    path: "/traces",
    validateSearch: (search) => ({
        trace: typeof search.trace === "string" ? search.trace : undefined,
        span: typeof search.span === "string" ? search.span : undefined,
    }),
    component: TracesPage,
});

const TraceDetailRoute = createRoute({
    getParentRoute: () => RootRoute,
    path: "/traces/$traceId",
    validateSearch: (search) => ({
        span: typeof search.span === "string" ? search.span : undefined,
    }),
    component: TraceDetailPage,
});

const AnalyticsRoute = createRoute({
    getParentRoute: () => RootRoute,
    path: "/analytics",
    component: AnalyticsPage,
});

const PublicAnalyticsRoute = createRoute({
    getParentRoute: () => RootRoute,
    path: "/public-analytics",
    component: PublicAnalyticsPage,
});

const EvalsRoute = createRoute({
    getParentRoute: () => RootRoute,
    path: "/evals",
    component: EvalsPage,
});

const InstructionsRoute = createRoute({
    getParentRoute: () => RootRoute,
    path: "/instructions",
    validateSearch: (search) => ({
        tab:
            search.tab === "editor" || search.tab === "test-chat"
                ? search.tab
                : undefined,
    }),
    component: InstructionsPage,
});

const SettingsRoute = createRoute({
    getParentRoute: () => RootRoute,
    path: "/settings",
    component: SettingsPage,
});

const routeTree = RootRoute.addChildren([
    IndexRoute,
    ChatRouteEntry,
    ChatsRoute,
    UsageRoute,
    TracesRoute,
    TraceDetailRoute,
    AnalyticsRoute,
    PublicAnalyticsRoute,
    EvalsRoute,
    InstructionsRoute,
    SettingsRoute,
]);

export const router = createRouter({
    routeTree,
    history: createHashHistory(),
});

declare module "@tanstack/react-router" {
    interface Register {
        router: typeof router;
    }
}
