#!/bin/bash

# Find comments in the virtual-assistant-private-front project
# Searches for JavaScript/TypeScript, CSS, and HTML comments

echo "=== Finding Comments in ~/Projects/virtual-assistant-private-front ==="
echo ""

# JavaScript/TypeScript single-line comments (//)
echo "--- Single-line comments (//) ---"
grep -rn --include="*.ts" --include="*.tsx" --include="*.js" --include="*.jsx" \
  "//.*" packages/ 2>/dev/null | grep -v "node_modules" | grep -v "http://" | grep -v "https://" | grep -v "eslint-disable"

echo ""
echo "--- Multi-line comments (/* ... */) ---"
# JavaScript/TypeScript/CSS multi-line comments
grep -rn --include="*.ts" --include="*.tsx" --include="*.js" --include="*.jsx" --include="*.css" \
  "/\*" packages/ 2>/dev/null | grep -v "node_modules"

echo ""
echo "--- HTML comments (<!-- ... -->) ---"
# HTML comments
grep -rn --include="*.html" --include="*.tsx" --include="*.jsx" \
  "<!--" . 2>/dev/null | grep -v "node_modules" | grep -v "dist-"

echo ""
echo "=== Done ==="
