# Auth

## Context
The internal Auth page authenticates staff users and provides a
registration path gated by an access token. It is shown whenever there is no
active authenticated user or when a session expires.

## Data Sources
- `POST /auth/login`
  - Body: `email`, `password`.
  - Response: `access_token`, `token_type`.
- `POST /auth/register`
  - Body: `name`, `email`, `password`, `confirm_password`, `registration_token`.
  - Response: `access_token`, `token_type`.
- `GET /auth/me` (after login) to load the current user profile.

## UI Structure
- Single card centered on the page.
- Title + helper text switch based on mode:
  - Login: “Sign in to continue” with sign-in helper text.
  - Register: “Register with access token” with registration helper text.
- Form fields
  - Login: email, password.
  - Register: name, email, password, confirm password, registration token.
- Primary submit button (Login/Register).
- Secondary mode toggle button (hidden when session expired).
- Session expired banner appears above the card when `sessionExpired=true`.
- Error alert for authentication failures.

## Validation Rules
- Register mode password validation:
  - Must match confirmation.
  - Minimum 12 characters.
  - Must contain uppercase, lowercase, and a number.
- Email is required and uses browser email validation.

## Behavior Notes
- When `sessionExpired` is true, the page forces login mode and shows a banner.
- Switching modes resets form state and clears errors.
- Successful login/register stores the token and triggers user profile load.
- Errors show in a destructive alert under the form.

## Extension Guidance
- Keep registration gated by tokens; do not expose public sign-up.
- Update this spec when auth endpoints or password rules change.
