# Chat Analytics

## Context
The Chat Analytics page provides operational analytics across internal and public
chats. It focuses on volume, engagement depth, and response performance. It is
not a conversion tracker.

## Data Source
- `GET /analytics/conversations`
  - Query params: `platform` (both|internal|public), `start`, `end`.
  - Returns totals, daily buckets (hourly for last 24 hours), length buckets + stats, response time buckets + stats, hourly activity.

## UI Structure
- Header controls
  - Platform toggle: Both / Internal / Public.
  - Time range filter (preset + custom range).
  - Clear action resets filters to defaults.
  - Refresh action.
- Summary cards
  - Total chats.
  - Total chat turns (messages).
  - Avg messages per chat.
- Charts
  - Chat volume (daily; hourly for last 24 hours).
  - Messages volume (daily; hourly for last 24 hours).
  - Chat length buckets + stats.
  - Response time buckets + stats.
  - Messages by hour (0–23).

## Behavior Notes
- Time range and platform filters apply to all charts and metrics.
- Filters persist in localStorage.
- Last 24 hours uses hourly buckets in the chat/message volume charts.
- Refresh re-fetches the data with current filters.

## Extension Guidance
- Add metrics that explain volume, engagement depth, and response performance.
- Avoid mixing operational cost/usage metrics into this page.
- Update this spec whenever data sources or UI sections change.
