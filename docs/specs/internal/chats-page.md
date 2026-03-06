# Chats

## Context
The Chats page is an internal operational view for reviewing chat history,
inspecting feedback, and scanning cost/activity across internal and public chats.
It is not a conversion tracker.

## Data Sources
- Chat list (paginated)
  - `GET /conversations/paginated`
  - Query params: `platform` (internal|public), `search`, `user_email`,
    `start`, `end`, `limit`, `offset`, `sort_by`, `descending`.
- Chat users (filter suggestions)
  - `GET /conversations/users`
  - Query params: `platform` (internal|public), `search`, `limit`.
- Chat detail
  - `GET /conversations/{conversation_id}`
- Trace detail (by assistant message)
  - `GET /usage/trace-by-message/{message_id}`
- Message feedback (detail view)
  - `GET /conversations/messages/{message_id}/feedback`
  - `POST /conversations/messages/{message_id}/feedback`
  - `DELETE /conversations/messages/feedback/{feedback_id}`
  - Access matches conversation visibility (owner for internal; ADMIN/DEV for public).
  - Update/delete requires feedback owner or ADMIN/DEV.

## UI Structure
- Header controls
  - Platform toggle: Both / Internal / Public.
  - User filter popover (searchable, supports public and internal users).
  - Time range filter (preset + custom range; defaults to last 30 days).
  - Search input (title + message content), debounced.
  - Clear action resets all filters (platform, user, time range, search).
  - Refresh action re-fetches the list with current filters.

- Table columns
  - Chat title + preview (search highlights applied).
  - User name + email (public uses consent data).
  - Platform badge.
  - Message count (sortable).
  - Cost (sortable).
  - Feedback up/down counts (sortable).
  - Updated timestamp (sortable, default sort: newest first).

- Detail sheet
  - Opens on row click and syncs to `chat` route param.
  - Header shows title, platform badge, updated timestamp.
  - Prev/Next controls move within the current page of results.
  - Summary toggle persists in localStorage.
  - Summary panel shows chat summary or placeholder if missing; panel is resizable above the transcript.
  - Transcript panel shows message history with per-message feedback controls.
  - Assistant messages include a Trace button that opens the trace debug view.

- Trace sheet
  - Opens from the Trace button on assistant messages.
  - Shows the trace debug view in summary-only mode for the selected message.

## Behavior Notes
- The browser tab title reflects the selected chat title; when no chat is selected it shows the page title.
- Filters (platform, user, time range, search) reset pagination to page 1.
- Search input is debounced before triggering list refresh.
- Search text highlights matching substrings in the table and transcript; a footer note appears in the detail sheet when highlighting is active.
- Filters and summary toggle persist in localStorage.
- When list data is loading, skeletons preserve row layout.
- Closing the sheet clears selection and removes the `chat` param.
- Feedback actions update counts in the list and the selected chat row.
- The trace sheet can be opened for assistant messages and refreshed on demand.

## Extension Guidance
- Keep the list fast and scannable; avoid heavy per-row widgets.
- New detail content should live in the sheet body, not the header description.
- Update this spec whenever filters, endpoints, or data columns change.
