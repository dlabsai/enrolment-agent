import { ShadowRootProvider } from "@va/shared/contexts/shadow-root-provider";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import shadowStyles from "@/widget.css?inline";

import { PublicApp } from "./components/app";

document.addEventListener("DOMContentLoaded", () => {
    const existingHost = document.querySelector("#chat-root");

    const host =
        existingHost instanceof HTMLElement
            ? existingHost
            : document.createElement("div");

    if (!(existingHost instanceof HTMLElement)) {
        host.id = "chat-root";
        document.body.append(host);
    }

    const shadowRoot = host.shadowRoot ?? host.attachShadow({ mode: "open" });

    const existingStyleElement = shadowRoot.querySelector(
        "style[data-chat-widget-styles]",
    );
    if (!existingStyleElement) {
        const styleElement = document.createElement("style");
        styleElement.dataset.chatWidgetStyles = "true";
        styleElement.textContent = shadowStyles;
        shadowRoot.append(styleElement);
    }

    const portalRoot = (function getPortalRoot(): HTMLDivElement {
        const existingPortalRoot = shadowRoot.querySelector(
            "#chat-widget-portal-root",
        );
        if (existingPortalRoot instanceof HTMLDivElement) {
            return existingPortalRoot;
        }
        const newPortalRoot = document.createElement("div");
        newPortalRoot.id = "chat-widget-portal-root";
        newPortalRoot.dataset.portalRoot = "true";
        shadowRoot.append(newPortalRoot);
        return newPortalRoot;
    })();

    const appContainer = (function getAppContainer(): HTMLDivElement {
        const existingAppContainer = shadowRoot.querySelector(
            "#chat-widget-app-root",
        );
        if (existingAppContainer instanceof HTMLDivElement) {
            return existingAppContainer;
        }
        const newAppContainer = document.createElement("div");
        newAppContainer.id = "chat-widget-app-root";
        newAppContainer.dataset.appRoot = "true";
        shadowRoot.append(newAppContainer);
        return newAppContainer;
    })();

    const root = host.__chatWidgetRoot ?? createRoot(appContainer);
    host.__chatWidgetRoot = root;

    root.render(
        <StrictMode>
            <ShadowRootProvider
                portalRoot={portalRoot}
                shadowRoot={shadowRoot}
            >
                <PublicApp />
            </ShadowRootProvider>
        </StrictMode>,
    );
});
