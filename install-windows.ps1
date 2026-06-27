Write-Host "=== KreativOS Installer ===" -ForegroundColor Cyan

# Python backend deps
pip install -r requirements.txt

# Frontend
Set-Location frontend
npm ci
npm run build
Set-Location ..

Write-Host "=== Done! Run: uvicorn backend.main:app --host 0.0.0.0 --port 8000 ===" -ForegroundColor Green
