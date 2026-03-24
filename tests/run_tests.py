"""
run_tests.py — Discover and run all tests in the tests/ directory.

Usage:
    python tests/run_tests.py
"""

import os
import sys
import unittest

# Ensure project root is on sys.path so 'src' imports work
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

if __name__ == '__main__':
    loader = unittest.TestLoader()
    suite = loader.discover('tests', pattern='test_*.py')
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
