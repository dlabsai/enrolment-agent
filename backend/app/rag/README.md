# RAG Data Pipeline

This document describes how to fetch and prepare RAG data for the backend.

## Fetching Source Data

Run these commands to fetch raw data from external sources:

```bash
# Fetch WordPress content
uv run -m app.rag.wordpress.cli

## Transforming Data

After fetching, transform the data for use in the RAG pipeline:

```bash
# Transform WordPress data
uv run -m app.rag.transform.transform_wp_data
```

## Building the Database

After transforming the data, build the search database by creating embeddings and populating the database:

```bash
# Build the search database (creates embeddings via Azure OpenAI)
uv run -m app.rag.build

# Force a full rebuild (deletes all documents and recreates from scratch)
uv run -m app.rag.build --force-rebuild

# Preview changes without committing to database
uv run -m app.rag.build --dry-run
```

## Order of Operations

1. Fetch WordPress content (`wordpress.cli`)
2. Transform WordPress data (`transform_wp_data`)
3. Build the search database (`build`)

## Note for Testing

Integration tests automatically build their own database in a persistent Docker container. You only need to ensure the source data files exist (steps 1-4 above). See the [Testing Guide](../../tests/README.md) for details.