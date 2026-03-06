# Instructions

## Context
The Instructions page lets admin/dev users manage prompt templates and versioned deployments. It provides an editor for instructions and a Test Chat panel for assistant versions. Application settings live on a separate Settings page.

## Layout
- Split workspace layout: left instructions sidebar, main editor, right Test Chat panel.
- Test Chat panel is collapsible and only appears for Assistant (Internal/Public) sections.
- Help guide modal explains the workflow and opens from the toolbar.

## Data Sources
### Instructions Editor
- `GET /prompts/disk-templates`
- `GET /prompts/versions?is_internal={bool}&scope={scope}`
- `GET /prompts/versions/deployed?is_internal={bool}&scope={scope}`
- `GET /prompts/versions/{version_id}`
- `POST /prompts/versions`
- `POST /prompts/versions/{version_id}/deploy`
- `POST /prompts/versions/undeploy?is_internal={bool}&scope={scope}`
- `DELETE /prompts/versions/{version_id}`

### Test Chat
- `POST /messages/internal/stream`
  - Uses selected assistant version (`prompt_set_version_id`) and optional chat context (`conversation_id`).

## Navigation Sidebar
- Single tree of sections (collapsible) and templates.
- Section scopes:
  - Assistant (Internal/Public)
  - Summary (Internal/Public)
  - Title (Internal/Public)
  - Title Transcript (Internal/Public)
  - RFI Extraction (Internal/Public if available)
- Assistant sections show Search, Chatbot, Guardrails templates.
- Helper sections show a single template.
- Modified templates show a yellow asterisk.

## Editor Area
### States
1. **No Selection**
   - Centered placeholder message with instructions.
2. **Template Selected (Edit Mode)**
   - Toolbar: version dropdown (Default + versions), Deploy/Delete, Diff toggle, Wrap lines, Reset (visible only when modified).
   - Right side: status badges, Save, Help.
   - CodeMirror editor with Jinja2 syntax highlighting.
3. **Version Selected (View Mode)**
   - Toolbar shows version info (number, name, creator).
   - Read-only list of modified prompts only, shown as diffs.

### Editor Features
- Jinja2 syntax highlighting, line numbers, bracket matching, fold gutter.
- Line wrap toggle (default enabled).
- Auto light/dark theme based on system preference.

## Save Dialog
- Opens from toolbar only when drafts exist.
- Version name (required) + description (optional).
- Modified instructions list.
- **Validation**:
  - Version name required.
  - At least one modified instruction in the active section.
  - Versions are scoped per section (Assistant, Summary, Title, Title Transcript, RFI Extraction).

## Test Chat Panel
- Header with collapse button (also toggled from toolbar).
- Controls row with Internal/Public selector and version dropdown.
- Version dropdown shows number, name, and “Live” badge if deployed.
- “New Chat” button appears after first message.
- Selecting a different test chat version clears messages and chat state.
- Only available for Assistant sections.

## Behavior Notes
- Active section/version selections persist in localStorage.
- Drafts persist across section changes and page refreshes.
- Each section remembers the last selected version (or Default) and restores it when revisited.
- Returning to the page reloads the selected version detail and the editor content for the active template (unless a draft exists).
- Selecting a new version or Default prompts confirmation if drafts exist in the active section.
- Switching versions clears drafts only for the active section; drafts in other sections are preserved.
- If a previously selected version is missing (deleted by another user), the selection resets to Default and an error message explains the version is no longer available.
- Section header selection loads versions/deployed status but does not change the selected template until a template is clicked.
- If no selection is persisted, the first available default template is auto-selected in priority order: Assistant internal (search → chatbot → guardrails), Assistant public, then helper templates.

## Network Behavior
### GET
| Endpoint | When |
| --- | --- |
| `/prompts/disk-templates` | Page load |
| `/prompts/versions?is_internal=...&scope=...` | Page load, section switch, Test Chat scope change |
| `/prompts/versions/deployed?is_internal=...&scope=...` | Page load, section switch |
| `/prompts/versions/{id}` | Version selection |

### POST
| Endpoint | When |
| --- | --- |
| `/prompts/versions` | Create version (active section) |
| `/prompts/versions/{id}/deploy` | Deploy version |
| `/prompts/versions/undeploy?is_internal={bool}&scope={scope}` | Reset to default |
| `/messages/internal/stream` | Send test chat message |

### DELETE
| Endpoint | When |
| --- | --- |
| `/prompts/versions/{id}` | Delete version |

## Persistence (localStorage)
Stored under `instructions-store` using Zustand persist:
- `hasSeenGuide`, `activePlatform`, `activeSectionId`, `expandedSections`, `selectedTemplate`
- `selectedVersionId`, `selectedVersionIdBySection`, `isDefaultSelected`, `isDefaultSelectedBySection`
- `drafts`, `wrapLines`, `isChatPanelOpen`

## Confirmation Dialogs
- Delete version
- Discard drafts when switching versions (active section only)
- Discard drafts when selecting Default (active section only)
- Reset template

## Errors
- Errors surface via a dismissible banner; drafts remain intact.
- Version load errors clear persisted selection; missing versions show a "no longer available" message and reset to Default.
- Test chat errors appear inline in the chat panel.
