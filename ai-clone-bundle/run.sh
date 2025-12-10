#!/bin/bash

# Ensure we are in the script's directory
cd "$(dirname "$0")"

# Check for python3
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 is not installed."
    exit 1
fi

# Create venv if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate venv
source .venv/bin/activate

# Install dependencies
echo "Installing/Updating dependencies..."
pip install -r requirements.txt

# Run the server
echo "Starting AI Clone Server..."
echo "Open http://localhost:3000 in your browser."
export PYTHONPATH=$PYTHONPATH:$(pwd)
python -m uvicorn ai_clone_server.app:app --host 127.0.0.1 --port 3000 --reload --reload-dir ai_clone_server
