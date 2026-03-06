# Internal App Shell

## Global error fallback

- The internal app must provide a global error boundary that catches render/runtime errors from the internal app tree.
- When the boundary catches an error, it must replace the app shell with a full-screen error view using the same styling as other internal page errors.
- The error view must display:
  - The error message when available and non-empty.
  - Otherwise, a generic message: "An unexpected error occurred."
- The error view must provide a retry action that attempts to re-render the app after the error state is cleared.
- When the boundary catches an error, it must log the error details for debugging.

## Scope

- This behavior applies to the internal app shell and is independent of per-page error handling.
