#!/bin/bash
set -e
echo "=== KreativOS Installer ==="

# Python backend deps
pip install -r requirements.txt

# Frontend
cd frontend
npm ci
npm run build
cd ..

echo "=== Done. Run: uvicorn backend.main:app --host 0.0.0.0 --port 8000 ==="
