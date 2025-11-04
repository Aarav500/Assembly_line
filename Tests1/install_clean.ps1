# Clean Install Script - Fixes ALL dependency issues
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Clean Dependency Installation" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$ErrorActionPreference = "Continue"

# Step 1: Uninstall CORRUPTED packages
Write-Host "`n[1/8] Removing corrupted packages..." -ForegroundColor Yellow
$corrupted = @(
    "torch", "torchvision", "torchaudio",
    "pandas", "numpy", "scipy",
    "flask", "werkzeug",
    "openai", "anthropic",
    "pydantic", "pydantic-core"
)

foreach ($pkg in $corrupted) {
    Write-Host "  Removing $pkg..." -ForegroundColor Gray
    pip uninstall -y $pkg 2>$null
}

# Step 2: Clear pip cache
Write-Host "`n[2/8] Clearing pip cache..." -ForegroundColor Yellow
pip cache purge

# Step 3: Upgrade pip, setuptools, wheel
Write-Host "`n[3/8] Upgrading pip tools..." -ForegroundColor Yellow
python -m pip install --upgrade pip setuptools wheel

# Step 4: Install core dependencies first (to avoid conflicts)
Write-Host "`n[4/8] Installing core dependencies..." -ForegroundColor Yellow
pip install --no-cache-dir "numpy==1.26.4"
pip install --no-cache-dir "pydantic==2.9.2" "pydantic-core==2.23.4"
pip install --no-cache-dir "typing-extensions==4.12.2"

# Step 5: Install web framework
Write-Host "`n[5/8] Installing Flask..." -ForegroundColor Yellow
pip install --no-cache-dir "flask==3.0.3" "werkzeug==3.0.4"

# Step 6: Install ML libraries (these take time)
Write-Host "`n[6/8] Installing ML libraries..." -ForegroundColor Yellow
Write-Host "  This may take 5-10 minutes..." -ForegroundColor Gray
pip install --no-cache-dir "torch==2.5.1" --index-url https://download.pytorch.org/whl/cpu
pip install --no-cache-dir "pandas==2.2.3"

# Step 7: Install all remaining packages
Write-Host "`n[7/8] Installing all requirements..." -ForegroundColor Yellow
Write-Host "  This will take 10-15 minutes..." -ForegroundColor Gray
pip install --no-cache-dir -r requirements-fixed.txt

# Step 8: Verify installation
Write-Host "`n[8/8] Verifying installation..." -ForegroundColor Yellow
pip check

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✅ SUCCESS! All dependencies installed correctly." -ForegroundColor Green
} else {
    Write-Host "`n⚠️  Some conflicts detected. Running conflict resolver..." -ForegroundColor Yellow

    # Fix common conflicts
    pip install --upgrade "protobuf<5.0.0,>=3.19.0"
    pip install --upgrade "grpcio>=1.48.0,<2.0.0"
    pip install --upgrade "certifi>=2023.7.22"

    Write-Host "`nRe-checking..." -ForegroundColor Gray
    pip check
}

# Display summary
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Installation Summary" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$packages = pip list --format=json | ConvertFrom-Json
Write-Host "`nTotal packages installed: $($packages.Count)" -ForegroundColor White

# Key packages
$key_pkgs = @("flask", "torch", "pandas", "numpy", "openai", "anthropic", "pytest")
Write-Host "`nKey packages:" -ForegroundColor White
foreach ($pkg in $key_pkgs) {
    $version = ($packages | Where-Object { $_.name -eq $pkg }).version
    if ($version) {
        Write-Host "  ✓ $pkg : $version" -ForegroundColor Green
    } else {
        Write-Host "  ✗ $pkg : NOT INSTALLED" -ForegroundColor Red
    }
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. cd D:\Assemblyline\unified_app" -ForegroundColor White
Write-Host "  2. python test_all.py" -ForegroundColor White
Write-Host "========================================" -ForegroundColor Cyan