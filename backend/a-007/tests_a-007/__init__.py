# Test package initialization
import sys
from pathlib import Path

# Ensure parent directory is in path for imports
test_dir = Path(__file__).parent
parent_dir = test_dir.parent

if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

# Also add the test directory itself
if str(test_dir) not in sys.path:
    sys.path.insert(0, str(test_dir))
