#!/bin/bash

set -e

# https://learn.microsoft.com/en-us/azure/app-service/
# https://learn.microsoft.com/en-us/azure/app-service/tutorial-python-postgresql-app-django?tabs=copilot&pivots=azure-developer-cli

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${ENV_FILE:-$SCRIPT_DIR/.deploy.env}"

if [ ! -f "$ENV_FILE" ]; then
    echo "Error: Env file not found at $ENV_FILE"
    echo "Create it (or copy .deploy.env.example) and re-run."
    exit 1
fi

# shellcheck disable=SC1090
source "$ENV_FILE"

: "${RESOURCE_GROUP:?Set RESOURCE_GROUP in $ENV_FILE}"
: "${WEBAPP_NAME:?Set WEBAPP_NAME in $ENV_FILE}"

POSTGRES_SERVER="${POSTGRES_SERVER:-}"
FRONTEND_DIR="${FRONTEND_DIR:-$SCRIPT_DIR/frontend}"
INTERNAL_FRONTEND_DIR="${INTERNAL_FRONTEND_DIR:-$(dirname "$SCRIPT_DIR")/virtual-assistant-private-front}"
DEPLOY_DIR="$SCRIPT_DIR/deploy-package"

# Enable PostgreSQL vector extension if server is specified
if [ -n "$POSTGRES_SERVER" ]; then
    echo "=== Enabling PostgreSQL Vector Extension ==="
    az postgres flexible-server parameter set \
        --resource-group "$RESOURCE_GROUP" \
        --server-name "$POSTGRES_SERVER" \
        --name azure.extensions \
        --value vector \
        --output none || echo "Warning: Could not enable vector extension (may already be enabled)"
fi

echo "=== Cleaning Previous Builds ==="
rm -rf "$DEPLOY_DIR"
rm -f "$SCRIPT_DIR/deploy.zip"

echo "=== Building Dev Frontend (virtual-assistant-private/frontend) ==="
cd "$FRONTEND_DIR"
npm ci
VITE_API_URL=/api VITE_PUBLIC_WIDGET_BASE_PATH=/public/ npm run build-public-local

echo "=== Building Internal Frontend (virtual-assistant-private-front) ==="
if [ -d "$INTERNAL_FRONTEND_DIR" ]; then
    cd "$INTERNAL_FRONTEND_DIR"
    npm ci
    npm run build-internal-stage
else
    echo "Error: Internal frontend not found at $INTERNAL_FRONTEND_DIR"
    exit 1
fi

echo "=== Creating Deployment Package ==="
mkdir -p "$DEPLOY_DIR"

# Copy backend files (excluding dev files, large data directories, and PDFs)
rsync -a --exclude='rag/data' --exclude='*.pdf' "$SCRIPT_DIR/backend/app" "$DEPLOY_DIR/"
cp "$SCRIPT_DIR/backend/alembic.ini" "$DEPLOY_DIR/"
cp "$SCRIPT_DIR/backend/README.md" "$DEPLOY_DIR/"

# Generate requirements.txt from uv (more reliable on Azure than uv.lock)
cd "$SCRIPT_DIR/backend"
uv export --no-dev --no-hashes | grep -v "^-e " > "$DEPLOY_DIR/requirements.txt"

# Copy public frontend build to static-public folder (served at /public)
cp -r "$FRONTEND_DIR/dist-public-local" "$DEPLOY_DIR/static-public"

# Copy internal frontend build to static-internal folder (served at /internal)
cp -r "$INTERNAL_FRONTEND_DIR/dist-internal-stage" "$DEPLOY_DIR/static-internal"

# Create startup script for Azure
# Note: With SCM_DO_BUILD_DURING_DEPLOYMENT, app runs from /tmp/<uid>, not /home/site/wwwroot
cat > "$DEPLOY_DIR/startup.sh" << 'EOF'
#!/bin/bash
# Run migrations from wherever the app is
python -m alembic upgrade head

# Start the app with gunicorn + uvicorn workers (use static_app which serves frontend)
gunicorn --bind=0.0.0.0:8000 --timeout 600 --workers 4 -k uvicorn.workers.UvicornWorker app.static_app:app
EOF
chmod +x "$DEPLOY_DIR/startup.sh"

echo "=== Creating ZIP Package ==="
cd "$DEPLOY_DIR"
zip -r ../deploy.zip . -x "*.pyc" -x "__pycache__/*" -x ".git/*"

echo "=== Deploying to Azure Web App ==="

# Enable build automation during deployment
az webapp config appsettings set \
    --resource-group "$RESOURCE_GROUP" \
    --name "$WEBAPP_NAME" \
    --settings SCM_DO_BUILD_DURING_DEPLOYMENT=1 \
    --output none

# Deploy with clean=true to remove old files
az webapp deploy \
    --resource-group "$RESOURCE_GROUP" \
    --name "$WEBAPP_NAME" \
    --src-path "$SCRIPT_DIR/deploy.zip" \
    --type zip \
    # --clean true

echo "=== Setting Startup Command ==="
az webapp config set \
    --resource-group "$RESOURCE_GROUP" \
    --name "$WEBAPP_NAME" \
    --startup-file "startup.sh"

echo "=== Deployment Complete ==="

# Cleanup
rm -rf "$DEPLOY_DIR"
rm -f "$SCRIPT_DIR/deploy.zip"
