import type { Alias, PluginOption } from "vite";

import {
    createSharedAliases as createSharedAliasesRuntime,
    sharedPlugins as sharedPluginsRuntime,
} from "../vite-runtime.js";

interface SharedAliasOptions {
    appRoot: string;
    sharedRoot: string;
}

export const sharedPlugins = (): PluginOption[] => sharedPluginsRuntime();

export const createSharedAliases = ({
    appRoot,
    sharedRoot,
}: SharedAliasOptions): Alias[] =>
    createSharedAliasesRuntime({
        appRoot,
        sharedRoot,
    });
