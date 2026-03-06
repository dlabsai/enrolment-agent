# Widget

## Context
The public Widget is an embedded chat experience for prospective students. It
runs inside a shadow DOM, launches from a floating “Chat” button, and collects
consent details before allowing messaging.

## Data Sources
- Send chat message
  - `POST /messages/public`
  - Body: `user_prompt`, optional `conversation_id`, `parent_message_id`.
  - Response returns `conversation_id`, `assistant_message_id`, `assistant_message`.
- Consent submission
  - `POST /consent`
  - Payload includes user details, `conversation_id`, `user_id`, `environment`.
  - Optional `widget_closed=true` when the widget closes.
  - Response: `{ success: boolean, message: string }`.
  - On failure returns **500** with `detail="Failed to save consent data"`.

## UI Structure
- Floating launcher
  - Fixed button in bottom-right labeled “Chat”.
  - Hidden while the widget panel is open.

- Chat panel
  - Fixed card (402px wide) on desktop; height clamps to `min(720px, calc(100vh - 3rem))` with 24px margin.
  - On small screens, the panel is centered with 16px margins and caps width at 402px.
  - Header with branding and actions: clear history, close widget.
  - Body switches between consent banner and chat transcript.
  - User message bodies render as plain text (no Markdown) but share the same base typography as assistant messages.
  - Assistant message bodies render Markdown with Streamdown (streaming-ready), using Streamdown's Tailwind styling (no custom chat markdown styles).
  - Footer shows admissions phone and “chat with our advisor” link.

- Consent banner
  - Form fields: first name, last name, email, phone, ZIP.
  - Validation:
    - First/last name required (min 2 characters).
    - Email required and must match a standard email pattern.
    - Phone required (10 digits; input formats as `(XXX) XXX-XXXX`).
    - ZIP required (5 digits).
  - Consent text includes privacy policy and terms links.

- Clear history dialog
  - Confirms before clearing chat history.

## Behavior Notes
- The widget mounts inside a shadow root at `#chat-root` and uses a portal root
  for dialogs within the shadow DOM.
- Visibility defaults to `VITE_VISIBLE_BY_DEFAULT` and persists only in memory.
- Closing the widget submits consent with `widget_closed=true` if consent data
  exists; it includes the latest chat id (`conversation_id`) when available.
- Chat history, chat id, parent message id, consent data, consent status,
  consent chat IDs, and a generated user id are stored in local storage.
- Consent must be completed before sending messages.
- Submitting the consent form sends consent for the current chat plus any stored
  chat IDs; on success the widget switches to chat.
- New chats submit consent for the new chat id (`conversation_id`) once per chat.
- Clear history resets stored messages, chat id, and parent message id.
- The public chat request is a single-response call; errors append a user-visible
  assistant error message to the transcript.

## Extension Guidance
- Keep the widget lightweight and embeddable.
- Avoid adding admin or analytics controls here.
- Update this spec whenever public endpoints or consent flow changes.
