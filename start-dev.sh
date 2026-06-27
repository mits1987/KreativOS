#!/bin/bash
echo "Starting KreativOS dev environment..."
# Backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
# Frontend
npm run dev &
FRONTEND_PID=$!
trap "kill $BACKEND_PID $FRONTEND_PID" EXIT
wait
