#!/usr/bin/env python3
"""Simple test runner for the Night Sky project.

Runs unittest discovery in the `tests/` directory and returns a non-zero
exit code if any test fails.
"""
import sys
import unittest


def main():
    loader = unittest.TestLoader()
    tests = loader.discover('tests')
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(tests)
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
