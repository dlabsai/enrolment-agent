# Public Analytics

## Context
The Public Analytics page focuses on public-widget lead capture and public usage trends.
It is used by admissions leadership to track public engagement volume and lead capture,
not conversions.

## Data Source
- `GET /analytics/public-usage`
  - Query params: `start`, `end`.
  - Returns daily public usage (hourly for last 24 hours) plus total leads.

## UI Structure
- Header controls
  - Time range filter (preset + custom range).
  - Clear action resets filters to defaults.
  - Refresh action.
- Summary cards
  - Total leads (unique captured emails).
- Charts
  - Leads over time (daily; hourly for last 24 hours).

## Behavior Notes
- Time range filters apply to all charts and metrics.
- Filters persist in localStorage.
- Last 24 hours uses hourly buckets in the leads chart.
- Refresh re-fetches the data with current filters.

## Extension Guidance
- Prefer metrics that explain public engagement volume and lead capture.
- Avoid adding internal operational metrics here.
- Update this spec whenever data sources or UI sections change.
