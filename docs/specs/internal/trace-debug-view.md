# Conversation Turn Trace Debug View

## Overview
Provide a developer-facing, on-demand trace viewer for a **single conversation turn**. The view must show a **chronological, flat, scrollable** account of what happened during the turn, including all LLM calls (search, chatbot, guardrails), tool calls, tool results, prompts, responses, timing, and token/cost accounting. It must be usable in both:

- the **Traces** page (internal traces UI), and
- an **on-demand** panel within the **Chats** page (only when opened by the user).

This view is a debugging aid for slow or incorrect turn behavior.

## Access & Visibility
- Internal users only (admin/dev context, same as traces page).
- The Chats page must only display the trace view **on demand** (e.g., drawer/panel).

## Data Requirements
Reference: https://opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai/

For each span in a trace, the view must support displaying:
- **Span identity**: span_id, parent_span_id, name, status (OK/Error)
- **Timing**: start_time, end_time, duration_ms
- **Model metadata**: gen_ai.request.model, gen_ai.provider.name
- **Token usage**:
  - gen_ai.usage.input_tokens
  - gen_ai.usage.output_tokens
  - gen_ai.usage.details.cache_read_tokens (if present)
- **Cost**: operation.cost (includes cached token cost when available)
- **Prompts & responses** (full content, no truncation by default):
  - gen_ai.request.prompt
  - gen_ai.request.messages / gen_ai.input.messages
  - gen_ai.response.text / gen_ai.response.message
  - gen_ai.response.messages / gen_ai.output.messages
- **Tools**:
  - gen_ai.request.tools
  - gen_ai.response.tool_calls
  - tool results payloads (gen_ai.tool.*)

If some fields are missing, the UI should still render the span and show placeholders ("-").

## Layout
### Two-column view (Traces page)
- **Left pane**: span tree / timeline as a **table of contents**.
- **Right pane**: a **flat, scrollable** view with all spans formatted in order.

### Summary-only view (Chats page)
- Renders only the **Chat Turn Summary** block (timing bars + totals).
- No span navigator or full span list.

### Left pane (TOC)
- Toggle between **Tree** and **Timeline** modes.
- Each row shows:
  - span name
  - agent/model label (if available)
  - duration
  - error indicator
- Timeline mode uses horizontal bars scaled to **trace total duration**.
- Clicking a span in the TOC **scrolls the right pane** to the corresponding span section.

### Right pane (Flat View)
- Spans appear **in chronological order** (by start_time).
- Each span section includes:
  - span name + status
  - start time, end time, duration
  - relative offset from turn start
  - full prompt / response / tool payloads
  - tokens and cost breakdown

### Summary timeline (Turn Debug)
- The summary view renders a **gantt-style timeline** with a **universal range** from trace start to trace end.
- The **first row** is the conversation turn span (labeled “Turn”).
- Subsequent rows include:
  - LLM spans (labeled “LLM”) for search, chatbot, guardrails, internal summary, etc.
  - Tool calls under search (labeled “Tool: <name>”).
  - Embedding calls under tools (labeled “Embeddings”).
  - DB spans under search tools (labeled “DB: <system>”).
- Rows are **color-coded** to distinguish agent LLM calls vs tools/embeddings/DB.
- LLM color mapping:
  - search → chart-2
  - chatbot → chart-1
  - guardrails → chart-4
  - internal summary → chart-1 (unless otherwise configured)
- Spans running **after** the turn (e.g., internal summary) still render on the same scale.
- Clicking a timeline row shows a detail block with:
  - offset from trace start
  - input/output/cache tokens
  - cost (if available)
- Payloads can be toggled open to show:
  - LLM prompts or request messages
  - embedding input text
  - tool call arguments and results
- Long sections may be **collapsed with “Show more”**, but must be fully viewable without truncation.

## Formatting & Content
- All text content (messages, prompts, tool results) is rendered as **Markdown**.
- Response message parts (including `thinking`) render as structured JSON when available.
- JSON payloads are rendered with an **expandable JSON tree** and scrollable preview.
  - Default expansion is limited to a shallow depth (2 levels) for initial render performance; depth is controlled by `JSON_TREE_EXPAND_DEPTH` in `frontend/packages/app-internal/src/traces/lib/trace-view-utils.ts`.
  - String values under **content** keys show a Markdown preview icon.
  - Clicking the icon opens a **large dialog** with Markdown-rendered content.
- App Metadata uses a **two-column key/value layout**.
- No child span nesting is required in the right pane; all spans are rendered in a single flat stream.

## Guardrails & Retries
- Guardrail retries produce multiple chatbot and guardrail spans.
- The view must present each attempt **in order**, and label them (e.g., Chatbot Attempt #1, Guardrails #1).

## Timing Visualization
- A **summary timing block** at the top of the right pane:
  - Turn total time
  - Search time
  - Guardrails total time
  - Chatbot total time (sum across attempts)
- Each summary entry includes a compact **gantt-style bar**.
- Each span section shows its **duration** and **relative offset** from the start of the turn.

## Token & Cost Accounting
- Each span section shows:
  - input tokens
  - output tokens
  - cache read tokens (if available)
  - cost
- A final **aggregated totals** section combines all spans in the turn.

## Chats Page Integration
- The trace debug view is **not shown by default** in Chats.
- When opened, it renders the **summary-only view** (no span navigator or full span list).
- Navigation from the chat turn to the trace view must clearly identify the related turn.

## Error States
- If no trace data is available, show a clear empty state.
- If the trace fetch fails, show a descriptive error and allow retry.
