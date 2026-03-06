# Traces

## Context
The Traces page provides an operational view into OpenTelemetry traces for chat
requests. It is used to inspect span timing, failures, and model/tool payloads
for both internal and public traffic.

## Data Sources
- Trace index
  - `GET /usage/trace-index`
  - Query params: `limit`, `offset`, `sort_by=latest_start`, `descending=true`,
    `ai_only`, `platform` (both|internal|public), `start`, `end`.
- Trace detail
  - `GET /usage/trace/{trace_id}`

## UI Structure
- Header controls
  - Platform toggle: Both / Internal / Public.
  - Time range filter (preset + custom range).
  - AI only switch (persists in local storage).
  - Clear action resets filters to defaults.
  - Refresh action.

- Trace table
  - Columns: time, trace id, root span name, platform, span count, duration, status.
  - Row selection opens trace detail sheet.
  - Pagination controls with page size.
  - Loading skeletons and empty state message.

- Trace detail sheet
  - Header shows trace id, platform badge, timestamp, duration, span count.
  - Actions: refresh trace, open in new tab, previous/next trace navigation.
  - Body has view tabs:
    - Raw: resizable split (span navigator + raw span JSON).
    - Structured: embeds the conversation turn debug view.
  - Raw span JSON supports:
    - Toggle to parse JSON-like strings into nested objects.
    - Markdown preview dialog for `content` fields that are plain strings.

- Trace detail page (new tab)
  - Route: `/traces/$traceId`.
  - Same content as the trace detail sheet (header metadata + Raw/Structured views).
  - Allows deep-linking to a trace outside the sheet.

## Behavior Notes
- Active trace and span sync to `trace` and `span` query params.
- `/traces/$traceId` uses the `span` query param for deep links.
- Changing filters resets pagination and clears selection.
- Tree view supports expand/collapse per span; timeline view shows span bars.
- AI-only and filter selections persist in localStorage.
- Tab choice for trace view (Raw vs Structured) persists in localStorage.
- Raw JSON parsing toggle persists in localStorage.

## Extension Guidance
- Keep the table performant and focused on trace metadata.
- New span detail views should live in the right panel.
- Update this spec whenever trace endpoints or table columns change.
