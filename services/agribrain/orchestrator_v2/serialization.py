"""Serialization helpers for immutable orchestrator contracts.

``dataclasses.asdict`` deep-copies leaf values.  That is unsafe for the
``MappingProxyType`` instances intentionally used by the scientific contracts:
their immutability is useful in memory, but they are not pickleable.  Traverse
dataclasses and mappings explicitly so canonical publications can retain those
contracts without weakening them to mutable dictionaries at construction time.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from enum import Enum
from typing import Any


def to_plain_data(value: Any) -> Any:
    """Return a JSON-oriented tree without deepcopying immutable leaves."""
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: to_plain_data(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, Mapping):
        return {
            str(key): to_plain_data(item)
            for key, item in value.items()
        }
    if isinstance(value, Enum):
        return to_plain_data(value.value)
    if isinstance(value, (list, tuple)):
        return [to_plain_data(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return [to_plain_data(item) for item in sorted(value, key=str)]
    return value
