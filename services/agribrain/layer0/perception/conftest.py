"""
Shared pytest conftest for all perception engine tests.

Ensures the repository root is on sys.path so that
`from services.agribrain.layer0.perception...` imports work
regardless of whether tests are run from:

  - the full repo root   → `py -m pytest services/...`
  - a perception subtree  → `py -m pytest` inside layer0/perception/
  - an extracted zip       → `py -m pytest` inside layer0/
  
This replaces the per-file sys.path hacks in individual test modules.
"""

import sys
import os

# Walk up from this conftest.py until we find the repo root
# (the directory that directly contains 'services/')
_here = os.path.dirname(os.path.abspath(__file__))
_candidate = _here
for _ in range(10):  # guard against infinite walk
    if os.path.isdir(os.path.join(_candidate, "services", "agribrain")):
        if _candidate not in sys.path:
            sys.path.insert(0, _candidate)
        break
    _parent = os.path.dirname(_candidate)
    if _parent == _candidate:
        break
    _candidate = _parent
