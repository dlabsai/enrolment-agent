# Chat

## Context
The Chat page is the internal operator chat experience. Users can start new chats,
resume prior chats, search across their chat history, and provide per-message feedback.

## Data Sources
- Chat list
  - `GET /conversations`
- Chat detail
  - `GET /conversations/{conversation_id}`
- Send message
  - `POST /messages/internal/stream` (SSE; emits `conversation`, `title_update`, `agent_stage` (stage/status), `tool_call` (tool/status/input/output/error), `thinking` (status/content), `assistant_message`, `error` events).
  - Supports new conversation (`conversation_id` omitted) or existing (`conversation_id` + `parent_message_id`).
  - Supports regeneration via `is_regeneration=true` (uses `parent_message_id` without creating a new user message).
- Optional per-turn model overrides: `chatbot_model`, `search_model`, `guardrail_model`, `chatbot_reasoning_effort`, `search_reasoning_effort`, `guardrail_reasoning_effort`.
  - Defaults to system configuration when overrides are omitted.
- Chat actions
  - `DELETE /conversations/{conversation_id}`
  - `PUT /conversations/{conversation_id}/title`
  - `POST /conversations/{conversation_id}/title/regenerate`
- Branch metadata
  - `GET /conversations/{conversation_id}/tree` (conversation tree + current branch path)
  - `PUT /conversations/messages/{message_id}/active-child` (switch active child branch)
- Chat search
  - `GET /conversations/search?search={query}&offset={n}&limit={n}`
- Model list
  - `GET /models`
- Message feedback
  - `GET /conversations/messages/{message_id}/feedback`
  - `POST /conversations/messages/{message_id}/feedback`
  - `DELETE /conversations/messages/feedback/{feedback_id}`
  - Access matches conversation visibility (owner for internal; ADMIN/DEV for public).
  - Update/delete requires feedback owner or ADMIN/DEV.

## UI Structure
### Layout
- Two-column layout: left chat list, right chat area.
- On mobile, chat list is hidden; a sheet opens it from the left.

### Chat List (Left)
- Actions: New chat, Search chats.
- Scrollable list of chats sorted by most recently updated.
- Infinite load as the user scrolls (batched rendering for long lists).
- Empty state: “No chats yet”.
- Error state with retry.
- Per-chat actions: rename, regenerate title, delete (non-temp items only).

### Search Dialog
- Command-style dialog with input and results list.
- Debounced search query (250ms).
- Result rows show title and message snippet with query highlights.
- Snippets are left-truncated with a literal "..." starting 8 characters before the first match; right truncation uses the UI's CSS truncation.
- The search results panel keeps a fixed height; empty/loading/error states are centered.
- Results lazy-load on scroll using offset/limit paging.
- On hover (or keyboard focus), show a relative updated timestamp on the right; text should truncate to make room.
- Selecting a result navigates to the chat.

### Chat Area (Right)
- Message transcript with timestamps.
- Composer with draft persistence per chat.
- Model selection state persists in local storage.
  - Current overrides: `va.internal.chat.model-config`.
  - Favorite models: `va.internal.chat.model-favorites`.
  - Presets: `va.internal.chat.model-presets`.
- When `ENABLE_CHAT_MODEL_SELECTOR` is true (internal flag), the composer exposes a model selection dialog for Search, Chatbot, and Guardrails.
  - Each target defaults to system configuration until changed.
  - Targets are switched with tabs; a reset action clears the target back to default.
  - The dialog includes a searchable list of models from `GET /models`.
  - Each model row includes a star toggle to add/remove the model from favorites; favorites render in a separate section.
  - Presets:
    - A preset selector includes a `Custom` option that represents the current ad-hoc selection.
    - Selecting a preset applies its saved models and reasoning-effort overrides.
    - Saving requires a non-empty name; saving with an existing name overwrites it.
    - Deleting uses a subtle icon button that opens a confirmation dialog before removing the preset.
    - Active preset is derived by matching the current selections against saved presets; when none match, the UI shows `Custom`.
  - For `gpt-5` models, an additional reasoning-effort selector is available.
    - `gpt-5`: `low`, `medium`, `high`
    - `gpt-5.1`: `none`, `low`, `medium`, `high`
    - `gpt-5.2`: `none`, `low`, `medium`, `high`, `xhigh`
- Loading state while assistant response is in progress (SSE delivers final message when ready).
- Loader shows AI Elements timeline: agent entries, reasoning summaries, and tool calls in the order received.
  - Agent labels shimmer while active and show a live duration timer that freezes when the agent ends.
  - Tool calls are compact by default; tool input/output/error details expand when opened.
  - Reasoning blocks render only when content exists.
- After a response, an activity icon in the assistant footer toggles the same timeline below the message (no spinner header). Reasoning auto-expands when opened and stays open unless the user collapses it.
- Activity timelines are fetched on demand per assistant message (icon click) to avoid eager per-message trace requests; SSE timelines for newly generated messages are cached per message.
- Activity panel open state is tracked per chat so switching chats preserves each chat’s open/closed selections.
- User message bodies render as plain text (no Markdown) but share the same base typography as assistant messages.
- Assistant message bodies render Markdown with Streamdown (streaming-ready), using Streamdown's Tailwind styling (no custom chat markdown styles).
- Message feedback controls on assistant messages:
  - Thumbs up/down.
  - Optional comment dialog.
  - Popover for other users’ feedback.
- Message controls:
  - Copy message action on user and assistant messages.
  - “Edit message” on user messages (disabled on the first user message in a thread).
  - “Regenerate message” on assistant messages.
  - Trace icon on assistant messages opens a trace sheet for the message.
  - Branch selector (prev/next) shown when a message has multiple children.

## Chat List Display
Each chat item shows:
- Title (updates as backend title updates stream in).
- Loading indicator while awaiting assistant response.
- Unread badge when new messages arrive in background chats.
- Overflow menu with rename, regenerate title, and delete actions (on hover).

### Ordering
Chats are ordered by most recent activity (newest at top).

## User Scenarios
### 1. Page Load
- Fetch chat list from server.
- Display chats sorted by most recent.
- No chat is selected initially (empty chat area).

### 2. Click Existing Chat
- Highlight the selected chat.
- Show loading state in chat area.
- Load and display messages when ready.
- Mark chat as read (remove unread badge).

### 3. Click "New Chat"
- If viewing other chat filters, switch to "My chats" first.
- Deselect any current chat.
- Clear chat area (show welcome message).
- Do not create a sidebar entry until the first message is sent.

### 4. Send First Message (New Chat)
- Add new chat item at the top.
- Show user message as title and loading spinner.
- After response:
  - Update last message preview.
  - Remove loading spinner.
  - Keep position at top.

### 5. Send Message in Existing Chat
- Show loading spinner on that chat.
- After response:
  - Update last message preview.
  - Remove loading spinner.
  - Move chat to top.

### 6. Send Message in Background Chat
- Show loading spinner on that chat.
- After response:
  - Update last message preview.
  - Remove loading spinner.
  - Show unread badge.
  - Move chat to top.

### 7. Delete Chat
- Show confirmation dialog.
- On confirm: remove from sidebar immediately.
- If deleted chat was selected: clear chat area.
- API call happens in background.

## Behavior Notes
- Selecting a chat updates the `chat` URL parameter; clearing selection removes it.
- Browser tab title reflects the selected chat title; when no chat is selected it shows the page title.
- New chat clears current selection and opens an empty thread.
- Title lifecycle for new chats:
  - UI sets title to first user message.
  - Backend returns an improved title asynchronously; UI updates when received.
  - After assistant response completes, a second title generation runs; UI updates when received.
- Titles can be renamed or regenerated from the chat list.
- Deleting a chat removes it from the list and clears selection if it was open.
- Feedback actions update both the transcript and chat metadata.
- Editing a user message creates a new branch from the parent assistant message and trims the visible transcript to that branch.
- Regenerating an assistant message creates a new assistant child on the same user message and trims the transcript to the regenerated branch.
- Branch switching updates the active child for the selected message and reloads the active transcript.

## Key Visual States
### Chat States
| State | Loading Spinner | Unread Badge | Position |
| --- | --- | --- | --- |
| Idle | No | No | Unchanged |
| Sending (selected) | Yes | No | Unchanged |
| Sending (background) | Yes | No | Unchanged |
| Response arrived (selected) | No | No | Move to top |
| Response arrived (background) | No | Yes | Move to top |

### Transitions
- New chat appears instantly (no flicker).
- Chat items keep stable identity (no unmount/remount).

## Scroll Behavior
### Scroll Position Rules
| Scenario | Scroll Target | Animation |
| --- | --- | --- |
| Open chat | Last user message with 16px gap from top | Instant |
| Switch chat | Last user message with 16px gap from top | Instant |
| User sends message | Last user message with 16px gap from top | Smooth |
| Assistant message arrives | Last user message with 16px gap from top | Smooth |
| Loading indicator text appears | Bottom | Smooth |

Details:
- When opening/switching, scroll positions the last user message at the top with 16px gap.
- Loading indicator text triggers smooth scroll to bottom unless the user scrolled up >100px.
- Chat area reserves a small empty space beneath the last message; loader renders inside it.
- A floating "scroll to bottom" button appears when >100px from bottom.

## Error Handling
- Message send error: show error in chat area, remove spinner, keep chat position.
- Chat load error: show error state in sidebar with retry.
- Delete error: show error dialog and keep chat in list.

## Extension Guidance
- Keep the chat area focused on messaging and feedback.
- Avoid adding heavy analytics here; use the “Chats” view for operational review.
- Update this spec whenever conversation endpoints or message interactions change.
