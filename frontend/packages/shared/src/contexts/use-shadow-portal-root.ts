import { use } from "react";

import { ShadowRootContext } from "./shadow-root-context";

export const useShadowPortalRoot = (): HTMLElement | undefined =>
    use(ShadowRootContext).portalRoot;
