# ============================================
#  Quick Fix for Assemblyline Environment
# ============================================

$ErrorActionPreference = "Continue"

Write-Host "`n" -ForegroundColor Cyan
Write-Host "  Fixing Assemblyline Environment" -ForegroundColor Cyan
Write-Host "" -ForegroundColor Cyan

# Fix 1: Recreate pytest.ini without BOM
Write-Host "`n[1/4] Fixing pytest.ini encoding..." -ForegroundColor Yellow

$pytestConfig = @"
[pytest]
testpaths = backend infrastructure
python_files = test_*.py
python_functions = test_*
addopts = --tb=short --disable-warnings --maxfail=5 -v
filterwarnings =
    ignore::DeprecationWarning
    ignore::PendingDeprecationWarning
"@

# Write without BOM using ASCII encoding
[System.IO.File]::WriteAllText("pytest.ini", $pytestConfig, [System.Text.Encoding]::ASCII)
Write-Host "   pytest.ini fixed" -ForegroundColor Green

# Fix 2: Resolve dependency conflicts
Write-Host "`n[2/4] Resolving dependency conflicts..." -ForegroundColor Yellow
Write-Host "  Cleaning up conflicting packages..." -ForegroundColor Gray

# Uninstall conflicting versions silently
$null = pip uninstall -y langchain langchain-core langchain-community sqlalchemy 2>&1

Write-Host "  Installing compatible versions..." -ForegroundColor Gray
pip install --no-cache-dir -q `
    "sqlalchemy==2.0.35" `
    "langchain-core==0.3.17" `
    "langchain==0.3.7" `
    "langchain-community==0.3.7"

if ($LASTEXITCODE -eq 0) {
    Write-Host "   Dependencies resolved" -ForegroundColor Green
} else {
    Write-Host "   Warning: Some issues during installation" -ForegroundColor Yellow
}

# Fix 3: Install missing LLM packages
Write-Host "`n[3/4] Installing missing packages..." -ForegroundColor Yellow

pip install --no-cache-dir -q `
    "openai==1.54.3" `
    "anthropic==0.39.0"

if ($LASTEXITCODE -eq 0) {
    Write-Host "   Missing packages installed" -ForegroundColor Green
} else {
    Write-Host "   Warning: Some packages may not have installed" -ForegroundColor Yellow
}

# Fix 4: Verify installation
Write-Host "`n[4/4] Verifying fixes..." -ForegroundColor Yellow

# Test pytest.ini
$testResult = python -m pytest --version 2>&1 | Out-String
if ($testResult -notmatch "unexpected line") {
    Write-Host "   pytest.ini: OK" -ForegroundColor Green
} else {
    Write-Host "   pytest.ini: FAILED" -ForegroundColor Red
}

# Test imports
$imports = @("flask", "torch", "pandas", "numpy", "openai", "anthropic", "sqlalchemy", "langchain")
$passed = 0
$failed = @()

foreach ($pkg in $imports) {
    $result = python -c "import $pkg" 2>&1
    if ($LASTEXITCODE -eq 0) {
        $passed++
    } else {
        $failed += $pkg
    }
}

Write-Host "   Imports: $passed/$($imports.Count) OK" -ForegroundColor $(if ($failed.Count -eq 0) { "Green" } else { "Yellow" })

# Summary
Write-Host "`n" -ForegroundColor Cyan
Write-Host "-------------------------------------------" -ForegroundColor Cyan
Write-Host "        Fix Summary" -ForegroundColor Cyan
Write-Host "-------------------------------------------" -ForegroundColor Cyan

if ($failed.Count -eq 0) {
    Write-Host "  All fixes successful!" -ForegroundColor Green
    Write-Host "`n  Next steps:" -ForegroundColor White
    Write-Host "    1. Run: python test_all.py" -ForegroundColor Cyan
    Write-Host "    2. Check: pip list | grep -E 'openai|anthropic|langchain'" -ForegroundColor Cyan
} else {
    Write-Host "  Status: Partial success" -ForegroundColor Yellow
    Write-Host "`n  Missing packages:" -ForegroundColor Yellow
    $failed | ForEach-Object { Write-Host "    - $_" -ForegroundColor Red }
    Write-Host "`n  Try installing manually:" -ForegroundColor White
    Write-Host "    pip install $($failed -join ' ')" -ForegroundColor Cyan
}

Write-Host "-------------------------------------------`n" -ForegroundColor Cyan

# Show installed package versions
Write-Host "Key Package Versions:" -ForegroundColor Cyan
$packages = pip list --format=json | ConvertFrom-Json
@("flask", "sqlalchemy", "langchain", "openai", "anthropic", "torch", "pytest") | ForEach-Object {
    $pkg = $packages | Where-Object { $_.name -eq $_ }
    if ($pkg) {
        Write-Host "  $($pkg.name): $($pkg.version)" -ForegroundColor White
    }
}
Write-Host ""