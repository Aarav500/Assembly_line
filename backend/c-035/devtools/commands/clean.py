import os
import shutil

from devtools import dev_command


@dev_command(help="Remove __pycache__ directories and *.pyc files")
def clean(path: str = "."):
    removed = 0
    for root, dirs, files in os.walk(path):
        # Remove __pycache__ directories
        if "__pycache__" in dirs:
            p = os.path.join(root, "__pycache__")
            try:
                shutil.rmtree(p)
                print(f"Removed {p}")
                removed += 1
            except Exception as e:
                print(f"Failed to remove {p}: {e}")
        # Remove .pyc files
        for f in files:
            if f.endswith(".pyc"):
                fp = os.path.join(root, f)
                try:
                    os.remove(fp)
                    print(f"Removed {fp}")
                    removed += 1
                except Exception as e:
                    print(f"Failed to remove {fp}: {e}")
    print(f"Done. Removed {removed} items.")

