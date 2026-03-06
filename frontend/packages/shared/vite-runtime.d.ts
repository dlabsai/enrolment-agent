import type { Alias, PluginOption } from "vite";

interface SharedAliasOptions {
    appRoot: string;
    sharedRoot: string;
}

export function sharedPlugins(): PluginOption[];
export function createSharedAliases(options: SharedAliasOptions): Alias[];
