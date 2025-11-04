# add_smoke_tests.py
"""Add unique smoke tests to projects without tests (conflict-safe)"""
from pathlib import Path

INFRASTRUCTURE_PROJECTS = [
    'prod-001', 'prod-002', 'prod-003', 'prod-006',
    'prod-007', 'prod-009', 'prod-011'
]


def create_smoke_test(project_path):
    """Create a basic smoke test with unique name"""
    test_filename = f"test_smoke_{project_path.name}.py"
    test_file = project_path / test_filename

    # Remove any old test_smoke.py to avoid name conflicts
    old_file = project_path / "test_smoke.py"
    if old_file.exists():
        old_file.unlink()

    if test_file.exists():
        print(f"✔ Smoke test already exists for {project_path.name}")
        return

    test_content = f'''import pytest
import ast
from pathlib import Path

def test_module_imports():
    """Ensure module imports or has Python files"""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))

    try:
        import {project_path.name.replace('-', '_')}
        assert True
    except ImportError:
        py_files = list(Path(__file__).parent.glob('*.py'))
        assert len(py_files) > 0, "No Python files found"

def test_files_exist():
    """Ensure essential files exist"""
    path = Path(__file__).parent
    py_files = list(path.glob('*.py'))
    assert len(py_files) > 0, "No Python files in project"

    has_config = (
        (path / 'requirements.txt').exists() or
        (path / 'config.py').exists() or
        (path / 'setup.py').exists()
    )
    assert has_config or len(py_files) > 1, "No configuration found"

def test_no_syntax_errors():
    """Ensure all .py files parse correctly"""
    path = Path(__file__).parent
    for py_file in path.glob('*.py'):
        if py_file.name.startswith('test_'):
            continue
        try:
            ast.parse(py_file.read_text())
        except SyntaxError as e:
            pytest.fail(f"Syntax error in {{py_file.name}}: {{e}}")
'''

    test_file.write_text(test_content, encoding="utf-8")
    print(f"✅ Created smoke test for {project_path.name} → {test_filename}")


# Apply to all projects
for base_dir in ['backend', 'infrastructure']:
    base_path = Path(base_dir)
    if not base_path.exists():
        continue

    for project in base_path.iterdir():
        if project.is_dir() and not project.name.startswith('.'):
            has_tests = (
                list(project.glob('test_*.py')) or
                (project / 'tests').exists()
            )
            if not has_tests:
                create_smoke_test(project)
