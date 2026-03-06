# Usage

## Context
The Usage Dashboard is for admins to monitor operational usage, spend, latency,
errors, and model mix across internal and public chat traffic. It is not a
conversion or engagement tracker.

## Data Sources
- `GET /usage/summary`
  - Query params: `platform` (both|internal|public), `start`, `end`, `models` (repeatable model/provider filter).
  - Returns summary totals, daily series (hourly for last 24 hours), model breakdown, and latest traces.
  - Latest traces drive the “Recent requests” table.

## UI Structure
- Header controls
  - Platform toggle: Both / Internal / Public.
  - Time range filter (preset + custom range).
  - Model/provider filter via command menu.
  - Clear action resets filters to defaults.
  - Refresh action.

- LLM Summary Cards
  - Total requests.
  - Total tokens.
  - Total cost.
  - Avg response latency.

- Embedding Summary Cards
  - Total embedding requests.
  - Total embedding tokens.
  - Total embedding cost.
  - Avg embedding latency.

- Charts
  - LLM usage over time (daily requests/tokens; hourly for last 24 hours).
  - LLM cost over time (daily cost; hourly for last 24 hours).
  - Embedding usage over time (daily requests/tokens; hourly for last 24 hours).
  - Embedding cost over time (daily cost; hourly for last 24 hours).

- Model Breakdown
  - Usage by model for the selected time range.

- Recent Requests Table
  - Latest traces (time, model, platform, tokens, cost, duration, status).
  - Uses platform label: Public / Internal / Unknown (null).

## Behavior Notes
- Time range, platform, and model/provider filters apply to all charts and the table.
- Filters persist in localStorage.
- Last 24 hours uses hourly buckets in the time-series charts.
- Refresh re-fetches the dashboard data with current filters.
- “Unknown” platform represents traces without a conversation context.
- Provider filters match model prefixes (openrouter, openai, azure).

## Extension Guidance
- Add new metrics only if they inform cost, reliability, or capacity planning.
- Keep the dashboard fast and operationally focused.
- Update this spec whenever data sources or sections change.
