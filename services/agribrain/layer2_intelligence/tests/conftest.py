"""
Layer 2 Intelligence Test Suite — Shared Configuration.

Registers custom pytest markers for clean test isolation.
"""

import pytest


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "golden: Pinning tests for production behavior")
    config.addinivalue_line("markers", "unit: Single-module unit tests")
    config.addinivalue_line("markers", "integration: Cross-module integration tests")
    config.addinivalue_line("markers", "invariant: Runtime invariant tests")
