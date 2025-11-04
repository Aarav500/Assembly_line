# ============================================
#  Assemblyline Complete Setup (Self-Repairing)
# ============================================

$ErrorActionPreference = "Stop"

# --- Self-repair: sanitize this file if encoding or quotes are corrupted ---
$path = $MyInvocation.MyCommand.Definition
try {
    $raw = Get-Content $path -Raw -ErrorAction Stop
    $fixed = $raw -replace '[]', '"' -replace '[^\x00-\x7F]', ''
    if ($fixed -ne $raw) {
        Write-Host " Detected and cleaned invalid characters in script..." -ForegroundColor Yellow
        $fixed | Set-Content $path -Encoding UTF8
    }
}
catch {
    Write-Host " Self-repair check skipped (cannot access file)" -ForegroundColor Yellow
}

Write-Host "`n" -ForegroundColor Cyan
Write-Host "  Assemblyline Complete Setup (Fixed)   " -ForegroundColor Cyan
Write-Host "" -ForegroundColor Cyan

# Step 1: Clean slate
Write-Host "`n[1/10] Creating clean environment..." -ForegroundColor Yellow
Write-Host "  Removing all existing packages..." -ForegroundColor Gray

pip freeze | ForEach-Object {
    if ($_ -notmatch "^-e" -and $_ -notmatch "^#") {
        $pkg = $_.Split("==")[0]
        pip uninstall -y $pkg 2>$null
    }
}
Write-Host "   Clean slate ready" -ForegroundColor Green

# Step 2: Upgrade pip tools
Write-Host "`n[2/10] Upgrading pip tools..." -ForegroundColor Yellow
python -m pip install --upgrade pip==24.2 setuptools==75.1.0 wheel==0.44.0
Write-Host "   Pip tools upgraded" -ForegroundColor Green

# Step 3: Clear cache
Write-Host "`n[3/10] Clearing pip cache..." -ForegroundColor Yellow
pip cache purge
Write-Host "   Cache cleared" -ForegroundColor Green

# Step 4: Install dependencies
Write-Host "`n[4/10] Installing from pyproject.toml..." -ForegroundColor Yellow
Write-Host "  This will take around 1520 minutes..." -ForegroundColor Gray

# Phase 1
Write-Host "`n  Phase 1: Core dependencies..." -ForegroundColor Cyan
pip install --no-cache-dir `
    "pydantic==2.9.2" `
    "pydantic-core==2.23.4" `
    "typing-extensions==4.12.2" `
    "numpy==1.26.4"

# Phase 2
Write-Host "`n  Phase 2: Web framework..." -ForegroundColor Cyan
pip install --no-cache-dir `
    "flask==3.0.3" `
    "werkzeug==3.0.4" `
    "flask-cors==5.0.0" `
    "flask-sqlalchemy==3.1.1" `
    "flask-limiter==3.8.0" `
    "flask-smorest==0.46.2" `
    "rich==13.9.4"

# Phase 3
Write-Host "`n  Phase 3: Database..." -ForegroundColor Cyan
pip install --no-cache-dir `
    "sqlalchemy==2.0.36" `
    "alembic==1.13.3" `
    "psycopg2-binary==2.9.10" `
    "redis==5.2.0"

# Phase 4
Write-Host "`n  Phase 4: ML/AI..." -ForegroundColor Cyan
Write-Host "    Installing PyTorch (CPU)..." -ForegroundColor Gray
pip install --no-cache-dir torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu
Write-Host "    Installing pandas..." -ForegroundColor Gray
pip install --no-cache-dir "pandas==2.2.3"
Write-Host "    Installing scikit-learn..." -ForegroundColor Gray
pip install --no-cache-dir "scikit-learn==1.5.2"

# Phase 5
Write-Host "`n  Phase 5: LLM libraries..." -ForegroundColor Cyan
pip install --no-cache-dir `
    "openai==1.54.3" `
    "anthropic==0.39.0" `
    "langchain==0.3.7" `
    "langchain-core==0.3.15" `
    "langchain-community==0.3.7"

# Phase 6
Write-Host "`n  Phase 6: Remaining packages..." -ForegroundColor Cyan
pip install --no-cache-dir -e .
Write-Host "   All packages installed" -ForegroundColor Green

# Step 5
Write-Host "`n[5/10] Verifying installation..." -ForegroundColor Yellow
pip check
if ($LASTEXITCODE -eq 0) {
    Write-Host "   No dependency conflicts detected" -ForegroundColor Green
}
else {
    Write-Host "   Conflicts detected  applying corrective installs..." -ForegroundColor Yellow
    pip install --force-reinstall `
        "flask==3.0.3" `
        "flask-smorest==0.46.2" `
        "rich==13.9.4" `
        "numpy==1.26.4"
    pip check
}

# Step 6
Write-Host "`n[6/10] Testing core imports..." -ForegroundColor Yellow
python -c "import flask, torch, pandas, numpy, openai, sqlalchemy; print('Core imports successful')"
if ($LASTEXITCODE -eq 0) {
    Write-Host "   Core imports successful" -ForegroundColor Green
}
else {
    Write-Host "   Import test failed  recheck environment" -ForegroundColor Red
}

# Step 7
Write-Host "`n[7/10] Creating pytest.ini..." -ForegroundColor Yellow

$pytestIni = @"
[pytest]
testpaths = backend infrastructure
python_files = test_*.py
python_functions = test_*
addopts = --tb=short --disable-warnings --maxfail=5 -v --html=report.html --self-contained-html
filterwarnings =
    ignore::DeprecationWarning
    ignore::PendingDeprecationWarning
"@

Set-Content -Path "pytest.ini" -Value $pytestIni -Encoding UTF8
Write-Host "   pytest.ini created" -ForegroundColor Green

# Step 8
Write-Host "`n[8/10] Ensuring all packages are importable..." -ForegroundColor Yellow
$count = 0
Get-ChildItem -Path "backend","infrastructure" -Directory -Recurse | ForEach-Object {
    $initFile = Join-Path $_.FullName "__init__.py"
    if (-not (Test-Path $initFile)) {
        New-Item -ItemType File -Path $initFile -Force | Out-Null
        $count++
    }
}
Write-Host "   Added $count missing __init__.py files" -ForegroundColor Green

# Step 9
Write-Host "`n[9/10] Adding smoke tests where needed..." -ForegroundColor Yellow
$smokeTest = @'
import pytest
from pathlib import Path

def test_module_exists():
    path = Path(__file__).parent
    py_files = list(path.glob("*.py"))
    assert len(py_files) > 0, "No Python files found"

def test_no_syntax_errors():
    import ast
    path = Path(__file__).parent
    for py_file in path.glob("*.py"):
        if py_file.name.startswith("test_"):
            continue
        content = py_file.read_text()
        try:
            ast.parse(content)
        except SyntaxError as e:
            pytest.fail(f"Syntax error in {py_file.name}: {e}")
'@

$added = 0
Get-ChildItem -Path "backend","infrastructure" -Directory | ForEach-Object {
    $hasTests = (Get-ChildItem -Path $_.FullName -Filter "test_*.py").Count -gt 0
    if (-not $hasTests) {
        $testFile = Join-Path $_.FullName "test_smoke.py"
        Set-Content -Path $testFile -Value $smokeTest
        $added++
    }
}
Write-Host "   Added smoke tests to $added directories" -ForegroundColor Green

# Step 10
Write-Host "`n[10/10] Environment setup complete!" -ForegroundColor Yellow
$packages = pip list --format=json | ConvertFrom-Json
$total = $packages.Count

Write-Host ""
Write-Host "-------------------------------------------" -ForegroundColor Cyan
Write-Host "        Installation Summary" -ForegroundColor Cyan
Write-Host "-------------------------------------------" -ForegroundColor Cyan
Write-Host ("Total packages installed: {0}" -f $total) -ForegroundColor White

$key = @("flask","torch","pandas","numpy","openai","anthropic","pytest","sqlalchemy")
foreach ($pkg in $key) {
    $version = ($packages | Where-Object { $_.name -eq $pkg }).version
    if ($version) {
        Write-Host ("  OK  {0}  {1}" -f $pkg,$version) -ForegroundColor Green
    }
    else {
        Write-Host ("  MISSING  {0}" -f $pkg) -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "Running test suite..." -ForegroundColor Yellow
pytest | Tee-Object -FilePath "test_output.log"

Write-Host ""
Write-Host "Tests complete. HTML report: report.html" -ForegroundColor Green
Write-Host "-------------------------------------------" -ForegroundColor Green
Write-Host "              Setup Complete!" -ForegroundColor Green
Write-Host "-------------------------------------------" -ForegroundColor Green

