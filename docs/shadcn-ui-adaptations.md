Shadcn/ui adaptations

This project uses shadcn/ui components under `packages/shared/src/components/ui` with
aliases configured in `components.json`.

Local adaptations vs upstream

- AI Elements components from Vercel are installed under `packages/shared/src/components/ai-elements` (loader, reasoning, tool, code-block, shimmer) with imports adjusted to use shared aliases.
- `packages/shared/src/components/ai-elements/code-block.tsx` uses Shiki core with a limited JSON-only grammar and GitHub light/dark themes to keep bundles small.
- `packages/shared/src/components/ai-elements/reasoning.tsx` adds a `disableAutoClose` prop to keep reasoning panels open when replaying activity details.
- `packages/shared/src/components/ai-elements/tool.tsx` wraps tool input/output content to allow long words to break within code blocks.
- The loading indicator is split into public/internal variants so AI Elements (and their heavy dependencies) only load in the internal app. Public builds alias `@va/shared/components/loading-indicator` to `packages/app-public/src/components/loading-indicator-public.tsx` in `packages/app-public/vite.config.ts`.

- `packages/shared/src/components/ui/form.tsx`: uses the upstream shadcn/ui form API with `FormLabel` and `FormDescription` included.
- `packages/shared/src/components/ui/scroll-area.tsx`: adds a `viewportRef` prop on `ScrollArea` to access the viewport element directly. The root component does not forward refs.
- `packages/shared/src/components/ui/textarea.tsx`:
    - Uses `React.ComponentPropsWithRef<"textarea">` so consumers can pass a `ref` (React 19 “ref as prop” style) without needing `forwardRef`.
    - Removes Tailwind’s `field-sizing-content` utility to avoid browser-dependent textarea sizing, since the chat composer uses JS-based autosizing.
    - Adds `selection:bg-primary selection:text-primary-foreground` so text selection highlight follows the active theme tokens.
- `packages/shared/src/components/ui/tooltip.tsx`:
    - Disables tooltip motion/transition classes so tooltips simply appear/disappear (no slide/zoom/fade).
- Shadow DOM support for the public widget:
    - Portal-based components (dialog, alert dialog, sheet, popover, dropdown, select, tooltip) read the portal container from `packages/shared/src/contexts/shadow-root-context.tsx` so overlays render inside the widget shadow root.
    - `packages/shared/src/index.css` duplicates Tailwind default CSS variables on `:host` to ensure borders, rings, and shadows render correctly in the shadow DOM.
    - Tooltip content/arrow uses a higher z-index to ensure it renders above the widget surface and overlays.
    - `packages/shared/src/components/ui/dialog.tsx`: `DialogContent` accepts a `portalContainer` prop to force the portal to render within a specific DOM subtree when needed (e.g., to inherit `.public` theme CSS variables).

Dependencies

- `react-hook-form` is required by `packages/shared/src/components/ui/form.tsx` and used
  in `packages/app-public/src/components/consent-banner.tsx`.

Internal app blocks

- The internal app shell follows the official shadcn/ui sidebar block pattern
  (based on `sidebar-07`) using `SidebarProvider`, `Sidebar`, and
  `SidebarInset` in `packages/app-internal/src/app/components/app.tsx`.
- The internal sidebar header replaces the static logo-only layout with a
  toggle-aware control: the left header icon swaps to the collapse icon on
  hover when the sidebar is collapsed (and only then is clickable), while the
  expanded sidebar shows a right-aligned toggle button. The header padding is
  adjusted in collapsed mode so the icon aligns with sidebar menu icons.
- Sidebar design tokens are defined in `packages/shared/src/index.css` with brand-color
  overrides under `.internal-theme`.

Chat sidebar scroll area

- The internal conversation list uses `ScrollArea` from shadcn/ui with a
  Tailwind override applied via `className` in
  `packages/app-internal/src/chat/components/conversation-list.tsx`.
- Reason: Radix wraps the viewport content in a `div` with
  `display: table; min-width: 100%`, which can widen the list and cause
  right-edge clipping when a scrollbar is present.
- Fix: the list applies `&[data-slot=scroll-area-viewport]>div` utilities to
  force the wrapper to `display: block` and `width: 100%`, plus gutter/padding
  to keep the scrollbar from overlapping content. This keeps the fix scoped to
  the conversation list and avoids changing the shared `ScrollArea` component.
