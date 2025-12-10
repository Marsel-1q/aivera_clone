#!/bin/bash
# Starts the Frontend Development Server (Vite).
# Useful for frontend/design work with Hot Module Replacement (HMR).

set -euo pipefail

# Move to the script directory
cd "$(dirname "$0")"

FRONTEND_DIR="frontend"

if [ ! -d "$FRONTEND_DIR" ]; then
  echo "Frontend directory not found: $FRONTEND_DIR"
  echo "Please ensure you have initialized the frontend project."
  exit 1
fi

echo "Starting Frontend Dev Server..."
cd "$FRONTEND_DIR"

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
  echo "Installing frontend dependencies..."
  npm install
fi

# Run dev server
npm run dev
