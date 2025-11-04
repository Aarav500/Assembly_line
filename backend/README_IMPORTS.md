# Module Import Guide

## The Problem
Your modules are trying to import from each other (like `from services import ...`), 
but Python can't find them because they're not in the Python path.

## The Solution

### Option 1: Use import_helper (Recommended)
Add this to the TOP of any file that imports other modules:

```python
from import_helper import setup_imports
setup_imports()

# Now you can import other modules
from services import something
from config import settings
```

### Option 2: Run from project root
Always run your modules from the project root directory:

```bash
# Instead of:
cd backend/a-001
python app.py

# Do this:
cd /path/to/project
python -m backend.a-001.app
```

### Option 3: Install in development mode
Install the project so Python knows where to find modules:

```bash
cd /path/to/project
pip install -e .
```

## Shared Modules
Common modules that multiple modules import are now in `_shared/`:
- services
- config  
- utils
- db/database
- models
- storage
- etc.

Move your shared code into these directories.
