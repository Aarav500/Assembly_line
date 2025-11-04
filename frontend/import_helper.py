"""
Import Helper
Add this to the top of any module that needs to import other modules:

    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
"""

import sys
from pathlib import Path

def setup_imports():
    """Setup Python path for imports"""
    current_dir = Path(__file__).parent
    parent_dir = current_dir.parent

    # Add to Python path
    for path in [current_dir, parent_dir]:
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)

# Auto-setup on import
setup_imports()
