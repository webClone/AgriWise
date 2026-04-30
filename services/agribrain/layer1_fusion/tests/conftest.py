"""
Layer 1 Fusion Test Suite — Shared Configuration.

Registers custom pytest markers for clean test isolation:
  - golden: Pinning tests that assert deterministic, reproducible behavior
  - unit: Single-module unit tests
  - integration: Cross-module integration tests
  - invariant: Runtime invariant enforcement tests

Usage:
  pytest layer1_fusion/ -m golden      # Run only golden tests
  pytest layer1_fusion/ -m "not golden" # Run everything else
"""

import pytest


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "golden: Pinning tests for production behavior")
    config.addinivalue_line("markers", "unit: Single-module unit tests")
    config.addinivalue_line("markers", "integration: Cross-module integration tests")
    config.addinivalue_line("markers", "invariant: Runtime invariant tests")
