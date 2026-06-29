<#
.SYNOPSIS
  KreativOS Windows Installer — sets up backend (Python) + frontend (Node) deps.
#>

$ErrorActionPreference = "Stop"
$Host.UI.RawUI.ForegroundColor = "Cyan"
Write-Host "=== KreativOS Installer (Windows) ==="
Write-Host ""

# ── Prerequisites ─────────────────────────────────────────────────────────────
$pass = $true

try {
    $pv = python --version
    Write-Host "  [OK]  Python $pv" -ForegroundColor Green
} catch {
    Write-Host "  [FAIL] Python not found — install Python 3.11+ from python.org" -ForegroundColor Red
    $pass = $false
}

try {
    $nv = node --version
    Write-Host "  [OK]  Node $nv" -ForegroundColor Green
} catch {
    Write-Host "  [FAIL] Node.js not found — install from nodejs.org" -ForegroundColor Red
    $pass = $false
}

if (-not $pass) { exit 1 }

# ── .env ──────────────────────────────────────────────────────────────────────
if (-not (Test-Path -LiteralPath ".env")) {
    Write-Host ""
    Write-Host "Creating .env from .env.example..."
    Copy-Item -LiteralPath ".env.example" -Destination ".env"
    Write-Host "  [OK]  .env created — edit OLLAMA_BASE_URL if needed" -ForegroundColor Green
} else {
    Write-Host "  [OK]  .env already exists" -ForegroundColor Green
}

# ── Python backend ────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "Installing Python dependencies..."
pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { Write-Host "pip install failed" -ForegroundColor Red; exit 1 }
Write-Host "  [OK]  Python deps installed" -ForegroundColor Green

# ── Frontend ──────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "Installing frontend dependencies..."
Push-Location frontend
try {
    npm ci
    Write-Host "  [OK]  Frontend deps installed" -ForegroundColor Green
    Write-Host ""
    Write-Host "Building frontend..."
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "npm run build failed" }
    Write-Host "  [OK]  Frontend built" -ForegroundColor Green
} finally {
    Pop-Location
}

# ── Done ──────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "=== All done ===" -ForegroundColor Green
Write-Host ""
Write-Host "  Start backend:   uvicorn backend.main:app --host 0.0.0.0 --port 8000" -ForegroundColor Yellow
Write-Host "  Start frontend:  cd frontend; npm run dev" -ForegroundColor Yellow
Write-Host "  Dev combo:       .\start-dev-windows.ps1" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Make sure Ollama is running at the URL in .env" -ForegroundColor Yellow
