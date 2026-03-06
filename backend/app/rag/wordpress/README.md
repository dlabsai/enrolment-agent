# WordPress Data Fetcher and Processor

## Purpose

This module fetches data from the WordPress site configured via `WORDPRESS_MIRROR_URL` (see `.env`) to supplement the RAG system with university content including blog posts, pages, and program information. It processes the fetched data by cleaning WordPress-specific markup and converting to Markdown.

## Current Implementation

### Data Sources

The module uses the WordPress REST API to fetch data from these endpoints:

-   `/wp-json/wp/v2/posts/` - Blog posts
-   `/wp-json/wp/v2/pages/` - WordPress pages
-   `/wp-json/wp/v2/categories/` - Categories for blog posts
-   `/wp-json/wp/v2/tags/` - Tags for blog posts
-   `/wp-json/wp/v2/media/` - Media files (images, etc.)
-   `/wp-json/wp/v2/programs/` - Programs

### Data Structure

Each data type contains specific fields following the WordPress REST API format:

-   **Posts**: ID, date, title, content, excerpt, categories, tags, featured media
-   **Pages**: ID, date, title, content, excerpt, parent, menu order, featured media
-   **Programs**: ID, date, title, content, slug, link, custom fields (ACF)
-   **Categories/Tags**: ID, name, slug, description, post count

### File Structure

```
src/va/rag/wordpress/
├── cli.py                       # Command-line interface
├── cleaner.py                   # Content cleaning utilities
├── config.py                    # Configuration constants
├── converter.py                 # Converts data to RAG format
├── export.py                    # Exports content to markdown/HTML
├── extraction.py                # Extracts metadata from content
├── json_io.py                   # JSON handling utilities
├── models.py                    # Pydantic models for WordPress data
├── shortcode_analyzer.py        # Analyzes Divi shortcodes (TODO: remove?)
├── shortcode_cleaning_analyzer.py # Verifies cleaning effectiveness (TODO: remove?)
└── wordpress_client.py          # WordPress API client with retry logic
```

#### Data Flow:

1. `cli.py` parses command-line arguments and initiates the process
2. `wordpress_client.py` fetches data from WordPress API
3. `converter.py` processes the fetched data into RAG format
4. `export.py` exports the processed data to markdown and HTML files

### Data Directory Structure

The `../data/wordpress` directory contains:

-   **Raw API Data**: `*_raw_page*.json` (e.g., `posts_raw_page1.json`)
-   **Data**: `*.json` (e.g., `posts.json`)
-   **Processed Data**: `*_processed.json` (e.g., `posts_processed.json`)
-   **Exported Files**: `export/markdown/` and `export/html/` with type-specific subdirectories

### Content Processing

The module processes WordPress content through these steps:

1. **WordPress Cleaning**: Removes scripts/styles/comments while keeping semantic HTML and shortcode tags
2. **Excerpt Processing**: Processes excerpts to provide valuable summaries
3. **HTML to Markdown Conversion**: Converts clean HTML to Markdown format
4. **Metadata Extraction**: Extracts categories, tags, and other metadata
5. **RAG Content Generation**: Creates standardized content objects
6. **Content Export**: Exports content as markdown and HTML files

### Shortcode Analysis (TODO: remove?)

The module includes optional tools for analyzing shortcode usage (helpful for Divi or other builders):

-   **shortcode_analyzer.py**: Analyzes shortcode usage across content types
-   **shortcode_cleaning_analyzer.py**: Verifies cleaning effectiveness

### Usage

```bash
# Fetch and process all data types
uv run -m app.rag.wordpress.cli

# Process existing data without fetching
uv run -m app.rag.wordpress.cli --process-only

# Fetch and process specific content types
uv run -m app.rag.wordpress.cli --posts --pages

# Export processed content as files
uv run -m app.rag.wordpress.cli --process-only --export-files

# Sample mode and URL replacement
uv run -m app.rag.wordpress.cli --sample 10 --replace-url
```

### Demo Instance (TODO: check if up to date. move section to other file?)

See `docs/wordpress-demo.md` for local WordPress demo setup, seeding, and a validation checklist.
WordPress and `wp-db` start with the base compose; `wp-cli` is only needed when seeding.

The `--replace-url` flag replaces mirror URLs (from `WORDPRESS_MIRROR_URL`) with true URLs (from `WORDPRESS_WEBSITE_URL`) in the processed content. This works for both regular links and breadcrumbs, ensuring all navigation elements reference the correct production domain.

Available command-line options:

-   **Fetch**: `--posts`, `--pages`, `--programs`, `--categories`, `--tags`, `--media`
-   **Retry**: `--retry-min-wait`, `--retry-max-wait`, `--max-retries`, `--skip-after`
-   **Process**: `--process`, `--process-only`, `--data-dir`, `--export-files`, `--replace-url`
-   **Sample**: `--sample`

### Data Inspection

For inspecting large JSON files:

```bash
# View JSON file with pretty formatting
jq '.' src/va/rag/data/wordpress/posts.json

# Extract specific fields
jq '.[] | {id, title, date}' src/va/rag/data/wordpress/posts.json

# Count items
jq 'length' src/va/rag/data/wordpress/posts.json
```

### Error Handling and Retry Mechanism

The WordPress client implements robust error handling for server issues:

1. **Configurable Retries**: Retry on 500 errors
2. **Skip After X Retries**: Allows skipping problematic pages
3. **Memory Exhaustion Detection**: Detects server memory issues

Default retry parameters:

-   Minimum wait time: 1 second
-   Maximum wait time: 3 seconds
-   Maximum retries: None (unlimited)
-   Skip after: None (never skip)
