# Legacy Orchestrator

> **⚠️ DEPRECATED** — This module is no longer in active use.

## Status

- **Replaced by:** `orchestrator_v2/run_entrypoint.py`
- **Quarantined on:** 2026-03-25

## Contents

- `orchestrator_v1.py` — Original monolithic orchestrator (deprecated)

## Why This Exists

This directory preserves the original orchestrator for reference. All production
traffic now routes through `orchestrator_v2`. Do not import from this module in
new code.
