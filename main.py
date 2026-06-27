name: KrestivOS CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  backend-tests:
    name: Backend Tests (Python)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - name: Install dependencies
        run: pip install -r backend/requirements.txt
      - name: Run tests
        run: |
          cd backend
          pytest tests/ -v --tb=short --timeout=30
        env:
          WORKSPACE_DIR: /tmp/krestivos_test

  frontend-lint:
    name: Frontend Lint & Format
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20', cache: 'npm', cache-dependency-path: frontend/package-lock.json }
      - name: Install dependencies
        run: cd frontend && npm install
      - name: Lint
        run: cd frontend && npm run lint || true   # warn only, don't fail CI on warnings
      - name: Format check
        run: cd frontend && npm run format:check || true

  frontend-build:
    name: Frontend Build
    runs-on: ubuntu-latest
    needs: frontend-lint
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20', cache: 'npm', cache-dependency-path: frontend/package-lock.json }
      - name: Install and build
        run: |
          cd frontend
          npm install
          npm run build
      - name: Upload build artifact
        uses: actions/upload-artifact@v4
        with:
          name: frontend-dist
          path: frontend/dist/

  docker-build:
    name: Docker Build Check
    runs-on: ubuntu-latest
    needs: [backend-tests, frontend-build]
    steps:
      - uses: actions/checkout@v4
      - name: Build backend image
        run: docker build -t krestivos-backend ./backend
      - name: Build frontend image
        run: docker build -t krestivos-frontend ./frontend
