#!/bin/bash

set -e

# Local script to test the production setup (both frontends served by FastAPI)
# This mimics the Azure deployment locally for testing before deploying

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
STATIC_INTERNAL_DIR="$BACKEND_DIR/static-internal"
STATIC_PUBLIC_DIR="$BACKEND_DIR/static-public"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

# Parse arguments
SKIP_BUILD=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-build)
            SKIP_BUILD=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--skip-build]"
            exit 1
            ;;
    esac
done

if [ "$SKIP_BUILD" = false ]; then
    echo "=== Building Public + Internal Frontends (virtual-assistant-private/frontend) ==="
    cd "$FRONTEND_DIR"
    npm install
    VITE_API_URL=/api VITE_PUBLIC_WIDGET_BASE_PATH=/public/ npm run build-public-local
    VITE_API_URL=/api npm run build-internal-local
fi

echo "=== Setting up static directories ==="
# Clean previous static dirs
rm -rf "$STATIC_INTERNAL_DIR" "$STATIC_PUBLIC_DIR"

# Copy internal frontend to static-internal (served at /internal)
if [ -d "$FRONTEND_DIR/dist-internal-local" ]; then
    cp -r "$FRONTEND_DIR/dist-internal-local" "$STATIC_INTERNAL_DIR"
    echo "Internal frontend copied to $STATIC_INTERNAL_DIR"
else
    echo "Warning: Internal frontend build not found at $FRONTEND_DIR/dist-internal-local"
fi

# Copy public frontend to static-public (served at /public)
if [ -d "$FRONTEND_DIR/dist-public-local" ]; then
    cp -r "$FRONTEND_DIR/dist-public-local" "$STATIC_PUBLIC_DIR"
    echo "Public frontend copied to $STATIC_PUBLIC_DIR"
else
    echo "Warning: Public frontend build not found at $FRONTEND_DIR/dist-public-local"
fi

echo "=== Starting FastAPI with static file serving ==="
echo ""
echo "Endpoints:"
echo "  - Landing page:    http://localhost:8000/"
echo "  - Internal app:    http://localhost:8000/internal"
echo "  - Public app:      http://localhost:8000/public"
echo "  - API:            http://localhost:8000/api"
echo ""

cd "$BACKEND_DIR"
uv run uvicorn app.static_app:app --reload --host 0.0.0.0 --port 8000
