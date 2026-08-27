import json
import os
from pathlib import Path
from typing import Dict, Any, Optional

def _find_contract_path() -> Path:
    # Try repository root packages/contracts first
    repo_root = Path(__file__).resolve().parents[3]
    repo_contract = repo_root / "packages" / "contracts" / "asmae_surface_alias_v1.json"
    if repo_contract.is_file():
        return repo_contract

    # Try local package fallback
    pkg_contract = Path(__file__).resolve().parent / "asmae_surface_alias_v1.json"
    if pkg_contract.is_file():
        return pkg_contract

    raise FileNotFoundError("asmae_surface_alias_v1.json contract file missing from deployment")

def _load_contract() -> Dict[str, Any]:
    contract_path = _find_contract_path()
    with open(contract_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if data.get("version") != "asmae_surface_alias_v1":
        raise ValueError(f"Unsupported alias contract version: {data.get('version')}")
    return data

_ALIAS_CONTRACT = _load_contract()
_ALIASES: Dict[str, str] = _ALIAS_CONTRACT.get("aliases", {})
_CANONICAL_TARGET: str = _ALIAS_CONTRACT.get("canonical_target", "ASMAE_POSTERIOR_CONCENTRATION")

def resolve_surface_key(key: str) -> str:
    """Resolves any deprecated or legacy surface key to its canonical key."""
    if not key:
        return key
    s_key = str(key).strip()
    return _ALIASES.get(s_key, s_key)

def is_deprecated_alias(key: str) -> bool:
    """Returns True if the given surface key is a deprecated alias."""
    if not key:
        return False
    return str(key).strip() in _ALIASES

def get_canonical_target() -> str:
    return _CANONICAL_TARGET
