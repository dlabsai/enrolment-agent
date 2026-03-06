import { createContext } from "react";

export interface ShadowRootContextValue {
    shadowRoot?: ShadowRoot;
    portalRoot?: HTMLElement;
}

export const ShadowRootContext = createContext<ShadowRootContextValue>({
    shadowRoot: undefined,
    portalRoot: undefined,
});
