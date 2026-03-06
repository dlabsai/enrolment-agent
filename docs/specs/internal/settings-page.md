# Settings

## Context
The Settings page lets admins override system-level application settings (university info and guardrails message). It is a standalone page accessible from the main sidebar.

## Layout
Single-column centered layout with a card containing all settings fields.

### Settings Card
#### Header
- Title: "Application settings"
- Description: "Override system-level settings. Leave fields empty to use system defaults."

#### Settings Fields
Each field shows a label, input, and helper text for the system value.

| Field | Input Type | Description |
| --- | --- | --- |
| University Name | Input | Name displayed in prompts |
| University Website URL | Input | Main university website URL |
| Admissions Phone | Input | Phone number for admissions office |
| Transcripts Email | Input | Email for transcript requests |
| Application URL | Input | URL for application portal |
| Accreditation URL | Input | URL for accreditation information |
| Guardrails Blocked Message | Textarea | Message shown when guardrails block response |

#### Field Behavior
- Empty field uses system value (shown as placeholder + helper text when a system value exists).
- Non-empty field overrides system value.
- System values come from environment variables.

#### Actions
| Button | State | Behavior |
| --- | --- | --- |
| Save | Enabled when modified | Saves overrides, shows toast |
| Reset to system values | Enabled when overrides exist | Clears overrides, shows toast |

### Toasts
- Save success: "Settings saved"
- Reset success: "Settings reset to system values"

### Loading State
- Centered spinner while fetching settings.

### Errors
- Error alert displayed above form fields.
- Form data preserved on error.

## Network Behavior
### GET
| Endpoint | When |
| --- | --- |
| `/settings` | Settings page open |

### POST
| Endpoint | When |
| --- | --- |
| `/settings` | Save overrides |

### DELETE
| Endpoint | When |
| --- | --- |
| `/settings` | Reset settings to defaults |
