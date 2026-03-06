# Testing Guide

This document covers the testing infrastructure for the backend, including how to run tests efficiently with persistent RAG data.

## Quick Start

```bash
# Run all tests (fast - reuses existing RAG data)
uv run pytest

# Run integration/e2e tests only (LLM required)
uv run pytest tests/chat/test_llm_conversation_turn.py -v -s

# Run LLM-as-judge evaluation tests
uv run pytest tests/chat/test_eval_chatbot.py -v -s

# Run guardrails evaluation tests
uv run pytest tests/chat/test_eval_guardrails.py -v -s

# Run search agent evaluation tests
uv run pytest tests/chat/test_eval_search.py -v -s

# Run specific test cases
uv run pytest tests/chat/test_eval_chatbot.py -v -s -T "greeting_response,accreditation_inquiry"

# Run with repeats for statistical confidence
uv run pytest tests/chat/test_eval_chatbot.py -v -s -R 3 -C 5

# Run with fresh database (removes persistent container)
uv run pytest --fresh-db

# Force rebuild RAG data (expensive - calls embedding API)
uv run pytest --rebuild-rag
```

## Pytest Markers

Tests are organized using pytest markers for selective test execution:

| Marker | Description |
|--------|-------------|
| `slow` | Tests that take a long time to run |
| `llm` | Tests that require LLM API calls (Azure OpenAI) |
| `eval` | LLM-as-judge evaluation tests |

```bash
# Run only fast unit tests (exclude LLM tests)
uv run pytest -m "not llm"

# Run only LLM tests
uv run pytest -m llm

# Run only evaluation tests
uv run pytest -m eval

# Run slow tests (includes llm, eval)
uv run pytest -m slow

# Combine markers (e.g., slow but not eval)
uv run pytest -m "slow and not eval"
```

## Test Categories

### Unit Tests
Standard unit tests that don't require external services or databases.

### Integration Tests (E2E)
End-to-end tests that call real LLMs and use a real PostgreSQL database with RAG data.

Located in: `tests/chat/test_llm_conversation_turn.py`

### LLM-as-Judge Evaluation Tests

These tests use an LLM judge to evaluate agent responses against defined criteria. They use a custom evaluation library (`app/evals`) that supports:
- **Repeats**: Run each test case multiple times for statistical confidence
- **Parallel execution**: Run cases concurrently with configurable concurrency
- **Detailed reports**: Pass rates, durations, and per-assertion statistics
- **Test case filtering**: Run specific test cases by ID

| Test File | Component Tested | Description |
|-----------|-----------------|-------------|
| `test_eval_chatbot.py` | Full chatbot pipeline | Tests the complete flow: search/extractor → chatbot → guardrails |
| `test_eval_guardrails.py` | Guardrails agent (isolated) | Tests if guardrails correctly identifies valid/invalid responses |
| `test_eval_search.py` | Search agent (isolated) | Tests if search agent uses RAG tools and returns grounded info |

**Common Options:**
- `-R N` / `--repeat=N`: Number of times to repeat each test case (default: 1)
- `-C N` / `--max-concurrency=N`: Maximum concurrent LLM calls (default: 5)
- `-T IDs` / `--test-cases=IDs`: Comma-separated list of test case IDs to run
- `-P N` / `--pass-threshold=N`: Minimum pass rate threshold (default: 0.9 = 90%)

```bash
# Run full pipeline tests with 3 repeats
uv run pytest tests/chat/test_eval_chatbot.py -v -s -R 3 -C 5

# Run guardrails tests for specific violations
uv run pytest tests/chat/test_eval_guardrails.py -v -s -T "dollar_amounts_violation,free_word_violation"

# Run search agent tests for program queries
uv run pytest tests/chat/test_eval_search.py -v -s -T "program_inquiry_general,program_inquiry_business"

# Run with lower pass threshold (80%)
uv run pytest tests/chat/test_eval_chatbot.py -v -s -R 5 -P 0.8
```

### Variables Extraction Tests
Tests for conversation variable extraction using LLM.

Located in: `tests/sync/test_llm_variables_extraction.py`

```bash
uv run pytest tests/sync/test_llm_variables_extraction.py -v -s
```

## Chatbot Flow Architecture

```
CHATBOT FLOW:
User Input --> Search Agent --> Chatbot Agent --> Guardrails --> Response
                   |                  ^              |
                   |                  |              |
              RAG Tools:         (retry chatbot+guardrails if fails,
              - retrieve_documents    up to 2 retries by default)
              - find_document_titles
              - find_document_chunks
              - list_wordpress_pages

ISOLATED COMPONENT TESTS:
┌─────────────────────────────────────────────────────────────────┐
│ test_eval_search.py                                             │
│ Tests search agent in isolation:                                │
│ - Does it use RAG tools?                                        │
│ - Is the response grounded in retrieved data?                   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ test_eval_guardrails.py                                         │
│ Tests guardrails agent in isolation:                            │
│ - Does it catch rule violations ($ amounts, "free", etc.)?      │
│ - Does it correctly pass valid responses?                       │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ test_eval_chatbot.py                                            │
│ Tests full pipeline end-to-end:                                 │
│ - Does the final response follow guidelines?                    │
│ - Is it grounded in RAG data?                                   │
└─────────────────────────────────────────────────────────────────┘
```

## Persistent RAG Data

RAG data population is expensive because it creates embeddings via Azure OpenAI API. The test infrastructure uses a **persistent Docker container** (`virtual-assistant-test-postgres`) that keeps RAG data between test sessions.

## Telemetry Database for Tests

LLM evals and other tests emit telemetry spans into `otel_span`. Tests set `TELEMETRY_DATABASE_URL` to the pre-test database settings, so telemetry is written to the normal dev database instead of the test container. Override `TELEMETRY_DATABASE_URL` if you want telemetry to go elsewhere.

## Troubleshooting

### Tests fail with "No RAG data found"
The container may have been removed. Run tests normally and wait for RAG population.

### Tests are slow every time
Check if the container is being removed between runs:
```bash
docker ps -a --filter "name=virtual-assistant-test-postgres"
```

### Need to update RAG data after source changes
```bash
uv run pytest --rebuild-rag tests/chat/test_llm_conversation_turn.py
```

### No RAG source data available
If RAG source data files are missing, see the [RAG Data Pipeline documentation](../app/rag/README.md).

### Container port conflicts
Remove the old container and let tests create a new one:
```bash
docker rm -f virtual-assistant-test-postgres
```
