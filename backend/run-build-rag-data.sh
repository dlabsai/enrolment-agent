#!/bin/bash

set -ex

uv run -m app.rag.wordpress.cli
uv run -m app.rag.transform.transform_wp_data
uv run -m app.rag.build

# python -m app.rag.wordpress.cli
# python -m app.rag.transform.transform_wp_data
# python -m app.rag.build
