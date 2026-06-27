#!/bin/bash
set -e
echo "=== KreativOS Installer ==="

# Install Python deps
pip install -r requirements.txt

# Install Node deps and build frontend
npm install
npm run build

echo "=== Done. Run: uvicorn main:app --host 0.0.0.0 --port 8000 ==="
