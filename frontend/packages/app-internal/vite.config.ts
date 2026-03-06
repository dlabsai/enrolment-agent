import path from "node:path";

import { createSharedAliases, sharedPlugins } from "@va/shared/vite";
import { defineConfig, loadEnv, type UserConfig } from "vite";
import { analyzer } from "vite-bundle-analyzer";

export default defineConfig(({ command, mode }): UserConfig => {
    const env = loadEnv(mode, process.cwd(), "");
    const parts = mode.split("-");
    const environmentName = parts[1] || "local";
    const rawEnvironment = environmentName.toLowerCase();
    const normalizedEnvironment = ["local", "stage", "prod"].includes(
        rawEnvironment,
    )
        ? rawEnvironment
        : "local";
    const outDirectory = path.resolve(
        __dirname,
        `../../dist-internal-${normalizedEnvironment}`,
    );
    const shouldAnalyze =
        env.VITE_BUNDLE_ANALYZE === "1" || env.VITE_BUNDLE_ANALYZE === "true";

    const internalBuildConfig = {
        outDir: outDirectory,
        rollupOptions: {
            input: {
                index: path.resolve(__dirname, "index.html"),
            },
        },
    };

    const nodeEnv = command === "build" ? "production" : "development";
    const sharedRoot = path.resolve(__dirname, "../shared/src");

    return {
        appType: "mpa",
        plugins: [
            ...sharedPlugins(),
            ...(command === "build" && shouldAnalyze
                ? [
                      analyzer({
                          analyzerMode: "json",
                          fileName: `bundle-analysis-internal-${normalizedEnvironment}`,
                          summary: false,
                      }),
                  ]
                : []),
        ],
        resolve: {
            alias: createSharedAliases({
                appRoot: __dirname,
                sharedRoot,
            }),
        },
        define: {
            __APP_ENV__: JSON.stringify(normalizedEnvironment),
            __APP_FLAVOR__: JSON.stringify("internal"),
            "process.env.NODE_ENV": JSON.stringify(nodeEnv),
        },
        publicDir: path.resolve(__dirname, "../shared/public"),
        base: "/",
        ...(command === "build"
            ? {
                  build: {
                      ...internalBuildConfig,
                      emptyOutDir: true,
                  },
              }
            : {
                  server: {
                      host: "0.0.0.0",
                      port: 5174,
                      cors: true,
                      open: false,
                      watch: {
                          usePolling: true,
                          interval: 500,
                      },
                  },
              }),
    };
});
