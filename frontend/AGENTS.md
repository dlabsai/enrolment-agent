## Project Overview

This is **Demo University Enrollment Agent (va)** - a React 19 + TypeScript 5 + Vite 7 + Tailwind CSS 4 application with two distinct platforms:

1. **Public** - A chat widget for prospective students embedded on the public website
2. **Internal** - An internal version for university staff

## Project Structure

Key paths:

- `packages/app-public/index.html`: Public widget Vite entrypoint
- `packages/app-internal/index.html`: Internal app Vite entrypoint
- `packages/app-public/src/{main.tsx,components/,hooks/,lib/,types/}`: Public widget
- `packages/app-public/src/components/app.tsx`: Public widget root component
- `packages/app-internal/src/main.tsx`: Internal entrypoint
- `packages/app-internal/src/app/components/`: Internal app shell (auth-gated root + layout/sidebar)
- `packages/app-internal/src/{auth,chat,chats,chat-analytics,public-analytics,instructions,settings,traces,usage}/{components,contexts,hooks,lib,types}/`: Internal feature areas
- `packages/app-internal/src/lib/`: Internal shared utilities
- `packages/shared/src/{components,components/ui,hooks,lib,types,contexts}/`: Cross-platform shared code
- `packages/app-internal/src/AGENTS.md`: Internal app-specific runbook (login URL, navigation selectors)

Rule of thumb:

- Put cross-platform UI/utilities in `packages/shared/src/`; keep platform-specific code in `packages/app-<platform>/src/`.
- Use `@va/shared/*` imports for shared code (wired via Vite and TS paths).
- For internal feature areas (`auth`, `chat`, `chats`, `chat-analytics`, `public-analytics`), prefer the same slice layout (`components/`, `contexts/`, `hooks/`, `lib/`, `types/`) for discoverability

## ShadcnUI

`npx shadcn@latest` to search, view, and add shadcn/ui components

Try to use vanilla components. If you need to change their code then document the change

## Tailwind

- Tailwind v4 is configured via CSS only (no per-app `tailwind.config.ts`).
- Public widget styles are generated from `packages/app-public/src/widget.css` (inlined into the shadow root) which imports `@va/shared/index.css` and declares `@source` globs for the app, shared package, and streamdown.
- Internal app styles are generated from `packages/app-internal/src/app.css` which imports `@va/shared/index.css` and declares `@source` globs for the app, shared package, and streamdown.

## Tooling

- Shared tooling devDependencies (TypeScript, Tailwind, terser, vite-bundle-analyzer, @types/*) live in `frontend/package.json`.
- Package scripts use `pnpm -w exec tsc` to run the hoisted TypeScript binary.
- ESLint import resolution uses `frontend/tsconfig.imports.json` as the single referenced config for workspace paths.

## Code Quality

- No `any` types or type assertions unless absolutely necessary
- Prefer `undefined` over `null`
