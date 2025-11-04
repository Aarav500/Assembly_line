#!/bin/bash
# Setup script for b-008

python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
if [ -f requirements.txt ]; then
    pip install -r requirements.txt
fi
echo "Setup complete for {module_path.name}"
