# Configuration for Snapshot Rollback Agent

# Directory where snapshots will be stored (relative to project root)
SNAPSHOT_DIR = ".snapshots"

# Directory representing the workspace/project under test (relative to project root)
WORKSPACE_DIR = "workspace"

# Default test command; runs Python's unittest discovery in workspace/tests
TEST_COMMAND = "python -m unittest discover -s tests -p '*_test.py'"

