"""
Shared pytest conftest for all perception engine tests.

Ensures the repository root is on sys.path so that
`from layer0.perception...` imports work
regardless of whether tests are run from:

  - the full repo root   -> `py -m pytest services/...`
  - a perception subtree  -> `py -m pytest` inside layer0/perception/
  - an extracted zip       -> `py -m pytest` inside layer0/
  
This replaces the per-file sys.path hacks in individual test modules.
"""

import sys
import os
