# Auth & Authorization Specification

## Scope
Defines authentication, role semantics, and authorization requirements for the backend API.
This spec is exhaustive; an implementation following it should match current behavior.

## Roles
- **PUBLIC**: unauthenticated public-widget user (no backing user row).
- **DEV**: superuser. Has all ADMIN and USER privileges.
- **ADMIN**: internal admin access (subset of DEV).
- **USER**: internal chat access only.

Role hierarchy:
- DEV > ADMIN > USER (PUBLIC is unauthenticated and has no internal access)

## Authentication
### Secure-by-default policy
- All endpoints require authentication by default.
- An endpoint must explicitly opt out of auth to allow unauthenticated access.
- Use `dependencies=[Depends(require_user_roles(...))]` on endpoints/routers to list allowed roles explicitly.
- Public endpoints should use `get_request_user` in their role checks to make the lack of auth explicit in code.

### Bearer Tokens
- Protected endpoints require `Authorization: Bearer <token>`.
- Tokens are issued by `/auth/register` and `/auth/login`.

### Refresh Tokens
- Refresh tokens are stored in an HttpOnly cookie.
- `/auth/refresh` rotates the refresh token and returns a new access token.
- `/auth/logout` clears the refresh cookie and revokes the token if present.

### Future work: token storage hardening (frontend)
The internal SPA currently stores the access token in `localStorage`. This is convenient but
exposes the token to XSS if untrusted scripts run in the page. Refresh token rotation is now
implemented, but access tokens are still long-lived and stored in localStorage.

Future hardening work should consider:
- Moving access tokens to HttpOnly, Secure cookies (JS can’t read them).
- Shorter access-token lifetime now that refresh rotation exists.
- Strict Content Security Policy (CSP) to reduce XSS impact.

### Token validation (`get_current_user`)
If a protected endpoint requires authentication:
1. If no credentials are provided → **401** with `detail="Authentication credentials required"` and `WWW-Authenticate: Bearer`.
2. If token is invalid → **401** with `detail="Invalid authentication credentials"` and `WWW-Authenticate: Bearer`.
3. If token resolves to a user that does not exist → **401** with `detail="User not found"` and `WWW-Authenticate: Bearer`.
4. If user exists but `is_active=false` → **401** with `detail="Inactive user"` and `WWW-Authenticate: Bearer`.

### Optional authentication (`get_request_user`)
Public endpoints resolve the current user via optional auth in role checks:
- If token is missing → return a public user object (`role=PUBLIC`, no ID).
- If token is invalid or expired → **401** with `detail="Invalid authentication credentials"`.
- If token is valid but user is missing/inactive → return a public user object.
- If the allowed roles list is PUBLIC-only, authenticated users are rejected.

### User object helpers
All request dependencies inject a single `User` object with a role field.
Helper methods available on the object:
- `is_public_user`
- `is_internal_user`
- `is_internal_admin_user`
- `is_internal_dev_user`

## Registration & Login
### POST `/auth/register`
Public endpoint.
- `registration_token` in request selects the role:
  - `DEV_REGISTRATION_TOKEN` → DEV
  - `ADMIN_REGISTRATION_TOKEN` → ADMIN
  - `USER_REGISTRATION_TOKEN` → USER
- Invalid token → **400** `detail="Invalid registration token"`.
- Password mismatch → **400** `detail="Passwords do not match"`.
- Weak password → **400** with validator message.
- Existing email → **400** `detail="Email already registered"`.
- Rate limit: **429** `detail="Too many registration attempts. Please try again later."` with
  `Retry-After` header.
- On success returns a token (`access_token`).
- Sets a refresh token cookie (HttpOnly, rotated on refresh).

### POST `/auth/login`
Public endpoint.
- Invalid credentials → **401** `detail="Incorrect email or password"`.
- Inactive user → **401** `detail="Inactive user"`.
- Rate limit: **429** `detail="Too many login attempts. Please try again later."` with
  `Retry-After` header.
- On success returns a token (`access_token`).
- Sets a refresh token cookie (HttpOnly, rotated on refresh).

### POST `/auth/refresh`
Public endpoint.
- Requires refresh token cookie.
- Returns a new access token and rotates the refresh token cookie.
- Invalid/expired refresh token → **401**.

### POST `/auth/logout`
Public endpoint.
- Revokes the refresh token (if present) and clears the refresh cookie.

### GET `/auth/me`
Requires authentication. Returns current user profile.

### GET `/health`
Public endpoint.
- Returns `true` when the API is reachable.

## Authorization Helpers
Any endpoint tagged below as requiring ADMIN or DEV must reject all others with **403**.
Any endpoint requiring ownership must reject non-owners with **403**, unless the spec explicitly
allows ADMIN/DEV override.

## Endpoint Authorization Matrix
### Public (no auth required — must be explicitly marked with optional auth dependency)
- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/logout`
- `POST /messages/public`
- `POST /consent`
- `GET /health`

Public endpoints that use `require_user_roles(get_request_user, PUBLIC)` reject authenticated
users. Endpoints without that dependency (e.g., refresh/logout) accept requests regardless of
access-token presence.

### Admin or Dev (ADMIN/DEV)
- `GET /settings`
- `POST /settings`
- `DELETE /settings`
- `GET /prompts/disk-templates`
- `GET /prompts/versions`
- `GET /prompts/versions/deployed`
- `GET /prompts/versions/{version_id}`
- `POST /prompts/versions`
- `POST /prompts/versions/{version_id}/deploy`
- `POST /prompts/versions/undeploy`
- `DELETE /prompts/versions/{version_id}`
- `GET /analytics/conversations`
- `GET /analytics/public-usage`
- `GET /usage/summary`
- `GET /usage/trace-index`
- `GET /usage/trace/{trace_id}`
- `GET /usage/trace-by-message/{message_id}`

### Authenticated (USER/ADMIN/DEV)
- `GET /auth/me`
- `POST /messages/internal/stream`
- `/conversations` (all subroutes)
- `GET /models`

## Internal Chat Authorization Rules
### `POST /messages/internal/stream`
- Requires authentication.
- If `conversation_id` is provided, it must belong to the current user.

### `GET /conversations`
- Requires authentication.
- Returns the current user’s internal conversations.

### `GET /conversations/search`
- Requires authentication.
- Only searches the current user’s conversations.

### `GET /conversations/users`
- Requires authentication.
- `platform=public` or `platform` omitted (public included) → ADMIN/DEV only.
- Internal user list visibility:
  - ADMIN/DEV: USER-role conversations + their own.
  - USER: only their own.

### `GET /conversations/paginated`
- Requires authentication.
- Public platform included → ADMIN/DEV only.
- Internal visibility:
  - ADMIN/DEV: USER-role conversations + their own.
  - USER: only their own.

### `GET /conversations/{conversation_id}`
- Requires authentication.
- If conversation is public → ADMIN/DEV only.
- If internal → owner or ADMIN/DEV.
- If internal and owner is missing → ADMIN/DEV allowed; USER denied.

### `PUT /conversations/{conversation_id}/title`
- Requires authentication.
- Conversation must be internal and owned by current user.

### `POST /conversations/{conversation_id}/title/regenerate`
- Requires authentication.
- Conversation must be internal and owned by current user.

### `DELETE /conversations/{conversation_id}`
- Requires authentication.
- Only the owner may delete.

### `GET /conversations/{conversation_id}/tree`
- Requires authentication.
- If conversation is public → ADMIN/DEV only.
- If internal → owner or ADMIN/DEV.

### `PUT /conversations/messages/{message_id}/active-child`
- Requires authentication.
- If conversation is public → ADMIN/DEV only.
- If internal → owner or ADMIN/DEV.

### Message feedback endpoints
- Requires authentication.
- Access requires the same conversation permissions as `GET /conversations/{conversation_id}/tree`.
- Update/delete operations require the feedback owner.
- Endpoints:
  - `POST /conversations/messages/{message_id}/feedback`
  - `GET /conversations/messages/{message_id}/feedback`
  - `DELETE /conversations/messages/feedback/{feedback_id}`

## Frontend Role Behavior (internal UI)
- DEV users can log into the internal frontend and are treated as admins for UI access.
