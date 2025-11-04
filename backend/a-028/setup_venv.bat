@echo off
REM Setup script for a-028

python -m venv venv
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
if exist requirements.txt (
    pip install -r requirements.txt
)
echo Setup complete for {module_path.name}
