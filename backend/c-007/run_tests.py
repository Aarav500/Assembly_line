#!/usr/bin/env python
"""Test runner script for cross-platform compatibility."""
import sys
import pytest

if __name__ == "__main__":
    sys.exit(pytest.main(["tests", "-v"]))
