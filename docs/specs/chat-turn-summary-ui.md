# Chat Turn Summary UI (ASCII)

## Overview

This spec captures the proposed layout for the Chat Turn Summary pane to reduce noise and surface the LLM response first.

## ASCII Layout

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Chat Turn Summary (trace 019c078d2e2420e85c2b2b41d44a11ae)                     │
│ Span: chat gpt-5.1 (chatbot) • 4.30s • model gpt-5.1 • azure • chat            │
│ Tokens: input 3,922 • cache 3,840 • output 187 • cost 0.0024525                │
├──────────────────────────────────────────────────────────────────────────────┤
│ Request                                                                        │
│ ┌──────────────────────────────────────────────────────────────────────────┐ │
│ │ [system] You are an Internal Knowledge Assistant for Demo University      │ │
│ │          employees…                                                       │ │
│ │ [user]   ai programs                                                       │ │
│ └──────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│ Response                                                                       │
│ ┌──────────────────────────────────────────────────────────────────────────┐ │
│ │ [assistant] (thinking) **Searching for AI programs**                       │ │
│ │   I need to call the function to find document chunks…                     │ │
│ │ [assistant] (tool call) find_document_chunks {"content_search_query":...} │ │
│ │ [tool]  find_document_chunks → [{"type":"wp_page","id":6,"title":"..."}] │ │
│ │ [assistant] (thinking) **Retrieving program information**                  │ │
│ │   I will retrieve documents for IDs wp_program 14 and 15…                  │ │
│ │ [assistant] (tool call) retrieve_documents {"wp_program_ids":[14,15],...} │ │
│ │ [tool]  retrieve_documents → [[{"type":"wp_program","id":15,"title":"..."}]]│ │
│ │ [assistant] To help you accurately, I need to clarify what the user means… │ │
│ └──────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Behavior Notes

- The pane defaults to the first LLM span (where `gen_ai.operation.name` is present).
- If the selected span is non-LLM, show a hint: "Select an LLM span to view request/response details."
- Only two content sections are shown: Request and Response.
- Request shows input tokens and cache tokens; Response shows output tokens and cost.
- The Response section surfaces whatever the span returned (tool calls/results and/or final assistant text).
- If the span has no response content, show "No response content for this span".
- When the span is an LLM call, render all request/response messages (system/user/assistant/tool call/tool result) in role order with clear labels and formatting, including multiple reasoning blocks when present.
- Future: show time-to-first-token once instrumentation provides a span attribute (not currently in OTel GenAI semconv).
