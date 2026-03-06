# WordPress Demo Instance

This guide sets up a local WordPress instance with demo content and wires the RAG pipeline to it.

## Quick Start

1. Start the base compose (includes WordPress + wp-db + Postgres):

```bash
docker compose up -d
```

2. Seed demo content and build the RAG data from the local WordPress instance:

```bash
make demo
```

Optional commands:

- Start WordPress services only: `make wp-up`
- Seed WordPress only: `make wp-seed`
- Build RAG only: `make rag`

Widget embedding:

- The demo WordPress site auto-loads the public chat widget via a mu-plugin.
- Configure the script URL with `WORDPRESS_WIDGET_SCRIPT_URL` (default: `http://localhost:8000/public/chat-widget.js`).
- Configure the widget API base with `VITE_API_URL` (default: `http://localhost:8000/api`).
- Ensure `BACKEND_CORS_ORIGINS` includes `http://localhost:8080` so consent/chat calls are allowed from WordPress.

Default admin credentials (override via env):

- URL: `http://localhost:8080/wp-admin`
- Username: `admin` (`WP_DEMO_ADMIN_USER`)
- Password: `admin` (`WP_DEMO_ADMIN_PASSWORD`)
- Email: `admin@example.com` (`WP_DEMO_ADMIN_EMAIL`)

### Full reset (WP + RAG)

To drop the WordPress DB, reseed content, and rebuild the RAG tables from scratch:

```bash
make reset
```

Use `make reset` interactively, or `cd wordpress-demo && ./cli.sh reset --force` for non-interactive runs.

## What Gets Seeded

- Pages: every Markdown file in `wordpress-demo/content/pages` (slug = filename, title = first-line H1 or filename fallback).
- Programs (custom post type): every Markdown file in `wordpress-demo/content/programs`, nested under the `Academic Programs` parent.

Seed content is sourced from Markdown files in `wordpress-demo/content` and converted to HTML during seeding. If the first line is a top-level H1, it is skipped because WordPress already renders the page title.

## Validation Checklist

Use this every time you demo the WordPress pipeline:

- `http://localhost:8080/wp-json/wp/v2/pages` returns the seeded pages
- `http://localhost:8080/wp-json/wp/v2/programs` returns the seeded programs
- `backend/app/rag/data/wordpress/pages.json` and `programs.json` exist after fetch
- `backend/app/rag/data/wordpress/processed/pages_processed.json` and `programs_processed.json` exist after transform
- `uv run -m app.rag.build --dry-run` reports WordPress pages/programs being processed

## Notes

- The demo sets the WordPress front page to the seeded Home page.
- The demo uses a custom post type `programs` registered via a mu-plugin in `wordpress-demo/mu-plugins`.
- To reset demo content, delete the `wp-data` and `wp-db-data` Docker volumes and re-run `make wp-seed` (or `cd wordpress-demo && ./cli.sh seed`).
- The seed command is idempotent and will skip if content was already seeded. Force re-seed with `WP_DEMO_FORCE_SEED=1`.
