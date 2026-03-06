"""Wrapper module that adds static file serving to the FastAPI app.

Used in production deployment to serve an SPA frontend alongside the API.

This module:
- Serves the frontend at /
- Serves the API at /api
- Serves static assets (JS, CSS, fonts, images) with proper caching headers
- Handles SPA routing by serving index.html for non-API, non-file routes
- Adds GZip compression for text-based responses
"""

import mimetypes
from pathlib import Path

from fastapi import Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware

from app.app import app
from app.core.config import settings

# Serve frontend static files from ../static-<target> relative to this file
# In deployment: deploy-package/static-internal and deploy-package/static-public
STATIC_INTERNAL_DIR = Path(__file__).parent.parent / "static-internal"  # /internal
STATIC_PUBLIC_DIR = Path(__file__).parent.parent / "static-public"  # /public

# Add GZip compression for responses > 500 bytes
# Compresses text/html, application/json, text/css, application/javascript, etc.
app.add_middleware(GZipMiddleware, minimum_size=500)


def _get_content_type(file_path: Path) -> str:
    """Get the MIME type for a file, with sensible defaults."""
    content_type, _ = mimetypes.guess_type(str(file_path))
    if content_type is None:
        # Default to binary for unknown types
        content_type = "application/octet-stream"
    return content_type


def _create_file_response(file_path: Path, cache_max_age: int = 0) -> FileResponse:
    """Create a FileResponse with proper headers."""
    headers: dict[str, str] = {}
    if cache_max_age > 0:
        headers["Cache-Control"] = f"public, max-age={cache_max_age}"
    return FileResponse(
        file_path, media_type=_get_content_type(file_path), headers=headers if headers else None
    )


def _create_public_wrapper_response() -> Response:
    html = (
        "<!doctype html>"
        '<html lang="en-US">'
        "<head>"
        '<meta charset="UTF-8" />'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0" />'
        "<title>Public Enrollment Agent</title>"
        "</head>"
        "<body>"
        '<div id="chat-root"></div>'
        '<script type="text/javascript" src="/public/chat-widget.js"></script>'
        "</body>"
        "</html>"
    )
    return Response(content=html, media_type="text/html")


def _create_root_landing_response() -> Response:
    html = (
        "<!doctype html>"
        '<html lang="en-US">'
        "<head>"
        '<meta charset="UTF-8" />'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0" />'
        "<title>Enrollment Agent</title>"
        "<style>"
        "body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;"
        "margin:2rem;line-height:1.5;color:#111;}"
        "a{color:#0a58ca;text-decoration:none}"
        "a:hover{text-decoration:underline}"
        ".card{border:1px solid #e5e7eb;border-radius:12px;padding:16px;max-width:520px}"
        "</style>"
        "</head>"
        "<body>"
        '<div class="card">'
        "<h1>Enrollment Agent</h1>"
        "<p>Select an app:</p>"
        "<ul>"
        '<li><a href="/public">Public app</a></li>'
        '<li><a href="/internal">Internal app</a></li>'
        "</ul>"
        '<p>The API is available at <a href="/api">/api</a> and docs at '
        '<a href="/docs">/docs</a>.</p>'
        "</div>"
        "</body>"
        "</html>"
    )
    return Response(content=html, media_type="text/html")


def _collect_root_static_files(static_dir: Path) -> set[str]:
    root_static_files: set[str] = set()
    if static_dir.exists():
        for item in static_dir.iterdir():
            if item.is_file():
                root_static_files.add(item.name)
    return root_static_files


def _mount_static_assets(static_dir: Path, mount_prefix: str, name_prefix: str) -> None:
    assets_dir = static_dir / "assets"
    icons_dir = static_dir / "icons"

    if assets_dir.exists():
        app.mount(
            f"{mount_prefix}/assets",
            StaticFiles(directory=assets_dir),
            name=f"{name_prefix}-assets",
        )

    if icons_dir.exists():
        app.mount(
            f"{mount_prefix}/icons", StaticFiles(directory=icons_dir), name=f"{name_prefix}-icons"
        )


INTERNAL_ROOT_STATIC_FILES = _collect_root_static_files(STATIC_INTERNAL_DIR)
PUBLIC_ROOT_STATIC_FILES = _collect_root_static_files(STATIC_PUBLIC_DIR)

_mount_static_assets(STATIC_INTERNAL_DIR, "/internal", "internal")
_mount_static_assets(STATIC_PUBLIC_DIR, "/public", "public")

# Internal build uses base "/", so serve its assets at the root as well.
_mount_static_assets(STATIC_INTERNAL_DIR, "", "internal-root")

# Collect all root-level static files for dev frontend
DEV_STATIC_FILES: set[str] = set()


@app.get("/{filename:path}")
async def serve_static_or_spa(filename: str) -> Response:
    """Serve internal/public frontend static files or fall back to SPA index.html.

    Priority:
    1. If path starts with API prefix, skip (already handled by API router)
    2. If path matches a root-level static file, serve it
    3. Otherwise, serve index.html for SPA client-side routing
    """
    # API routes are already handled by the router mounted earlier
    api_prefix = settings.API_STR.lstrip("/")
    if filename.startswith(api_prefix):
        return Response(
            content='{"detail": "Not Found"}', status_code=404, media_type="application/json"
        )

    if filename == "":
        return _create_root_landing_response()

    if filename == "internal" or filename.startswith("internal/"):
        if not STATIC_INTERNAL_DIR.exists():
            return Response(
                content="Internal frontend not found", status_code=404, media_type="text/plain"
            )
        relative_path = filename.removeprefix("internal").lstrip("/")
        if relative_path in INTERNAL_ROOT_STATIC_FILES:
            file_path = STATIC_INTERNAL_DIR / relative_path
            if file_path.exists():
                cache_time = (
                    86400 if relative_path.endswith((".ico", ".png", ".jpg", ".svg")) else 3600
                )
                return _create_file_response(file_path, cache_max_age=cache_time)
        if relative_path and "." in relative_path.split("/")[-1]:
            return Response(content="Not Found", status_code=404, media_type="text/plain")
        index_path = STATIC_INTERNAL_DIR / "index.html"
        if index_path.exists():
            return _create_file_response(index_path, cache_max_age=0)
        return Response(content="Application not found", status_code=404, media_type="text/plain")

    if filename == "public" or filename.startswith("public/"):
        if not STATIC_PUBLIC_DIR.exists():
            return Response(
                content="Public frontend not found", status_code=404, media_type="text/plain"
            )
        relative_path = filename.removeprefix("public").lstrip("/")
        if relative_path == "":
            index_path = STATIC_PUBLIC_DIR / "index.html"
            if index_path.exists():
                return _create_file_response(index_path, cache_max_age=0)
            if (STATIC_PUBLIC_DIR / "chat-widget.js").exists():
                return _create_public_wrapper_response()
        if relative_path in PUBLIC_ROOT_STATIC_FILES:
            file_path = STATIC_PUBLIC_DIR / relative_path
            if file_path.exists():
                cache_time = (
                    86400 if relative_path.endswith((".ico", ".png", ".jpg", ".svg")) else 3600
                )
                return _create_file_response(file_path, cache_max_age=cache_time)
        if relative_path and "." in relative_path.split("/")[-1]:
            return Response(content="Not Found", status_code=404, media_type="text/plain")
        index_path = STATIC_PUBLIC_DIR / "index.html"
        if index_path.exists():
            return _create_file_response(index_path, cache_max_age=0)
        if (STATIC_PUBLIC_DIR / "chat-widget.js").exists():
            return _create_public_wrapper_response()
        return Response(content="Application not found", status_code=404, media_type="text/plain")

    return Response(content="Not Found", status_code=404, media_type="text/plain")
