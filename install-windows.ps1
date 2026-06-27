Write-Host "=== KreativOS Installer ===" -ForegroundColor Cyan

# Install Python deps
pip install -r requirements.txt

# Install Node deps and build frontend
npm install
npm run build

Write-Host "=== Done! Run: uvicorn main:app --host 0.0.0.0 --port 8000 ===" -ForegroundColor Green
