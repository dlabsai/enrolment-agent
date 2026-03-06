import path from "node:path";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";

export const sharedPlugins = () => [react(), tailwindcss()];

export const createSharedAliases = ({ appRoot, sharedRoot }) => {
    const resolvedSharedRoot = path.resolve(sharedRoot);
    const resolvedAppRoot = path.resolve(appRoot, "src");
    const aliases = [
        {
            find: "@va/shared",
            replacement: resolvedSharedRoot,
        },
        {
            find: "@",
            replacement: resolvedAppRoot,
        },
    ];

    return aliases;
};
