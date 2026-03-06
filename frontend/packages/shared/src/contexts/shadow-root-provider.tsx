import { type JSX, type ReactNode, useMemo } from "react";

import {
    ShadowRootContext,
    type ShadowRootContextValue,
} from "./shadow-root-context";

interface ShadowRootProviderProps {
    children: ReactNode;
    shadowRoot?: ShadowRoot;
    portalRoot?: HTMLElement;
}

export const ShadowRootProvider = ({
    children,
    shadowRoot,
    portalRoot,
}: ShadowRootProviderProps): JSX.Element => {
    const value = useMemo(
        (): ShadowRootContextValue => ({ shadowRoot, portalRoot }),
        [shadowRoot, portalRoot],
    );

    return <ShadowRootContext value={value}>{children}</ShadowRootContext>;
};
