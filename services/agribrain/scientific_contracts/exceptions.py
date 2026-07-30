"""Scientific Contracts — Core Exceptions.

Isolated from world_model, layer05_asmae, and layer10_sire.
"""

from __future__ import annotations


class ContractViolation(ValueError):
    """Raised when a scientific contract or ledger schema invariant is violated."""
    pass


class Layer10PublicationConstructionError(RuntimeError):
    """Raised when Layer 10 resolver, inventory, or display state construction fails."""
    pass
