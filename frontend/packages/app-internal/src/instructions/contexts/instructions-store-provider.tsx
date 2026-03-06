import { type JSX, type ReactNode, useMemo } from "react";

import { useAuthenticatedApi } from "../../auth/hooks/use-authenticated-api";
import { createInstructionsStore } from "../lib/store";
import { InstructionsStoreContext } from "./instructions-store-context";

interface InstructionsStoreProviderProps {
    children: ReactNode;
}

export const InstructionsStoreProvider = ({
    children,
}: InstructionsStoreProviderProps): JSX.Element => {
    const api = useAuthenticatedApi();

    // Create store once - api is stable after authentication so useMemo runs once
    const store = useMemo(() => createInstructionsStore(api), [api]);

    return (
        <InstructionsStoreContext value={store}>
            {children}
        </InstructionsStoreContext>
    );
};
