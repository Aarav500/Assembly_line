# auto_fix_imports.py
"""Auto-fix common import and setup errors"""
import json
import subprocess
import re
from pathlib import Path


def fix_import_errors():
    """Fix all import-related failures"""

    results = json.load(open('test_results.json'))
    import_failures = []

    for r in results:
        if 'FAIL' in r['status'] and r.get('tests', 0) == 0:
            # Likely import error
            import_failures.append(r)

    print(f"Found {len(import_failures)} import failures")

    for project in import_failures:
        name = project['name']
        output = project['output']

        # Find the project directory
        for base in ['backend', 'infrastructure', 'frontend']:
            path = Path(base) / name
            if path.exists():
                break
        else:
            print(f"❌ Can't find: {name}")
            continue

        print(f"\n🔧 Fixing: {name}")

        # Fix 1: Missing __init__.py
        init_file = path / '__init__.py'
        if not init_file.exists():
            init_file.write_text('')
            print("  ✓ Created __init__.py")

        # Fix 2: Missing imports in test files
        for test_file in path.glob('test_*.py'):
            content = test_file.read_text()

            # Add missing imports
            if 'import pytest' not in content:
                content = 'import pytest\n' + content
                test_file.write_text(content)
                print(f"  ✓ Added pytest import to {test_file.name}")

            # Fix relative imports
            if 'from . import' in content:
                content = content.replace('from . import', 'from backend.' + name + ' import')
                test_file.write_text(content)
                print(f"  ✓ Fixed relative imports in {test_file.name}")

        # Fix 3: Missing conftest.py
        conftest = path / 'conftest.py'
        if not conftest.exists():
            conftest.write_text('''
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
''')
            print("  ✓ Created conftest.py")

        print(f"  ✅ Fixed {name}")


if __name__ == '__main__':
    fix_import_errors()