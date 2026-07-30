import copy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from layer9_interface.schema import Layer9Input

@dataclass(frozen=True)
class ReportContextSnapshot:
    """An immutable, deep-copied snapshot of all reporting inputs."""
    l9_input: Layer9Input
    plots: List[Dict[str, Any]] = field(default_factory=list)
    region_id: Optional[str] = None
    role: str = "admin_auditor"

    def __post_init__(self):
        # Enforce deep-copy inside frozen dataclass via setattr
        object.__setattr__(self, "l9_input", copy.deepcopy(self.l9_input))
        object.__setattr__(self, "plots", copy.deepcopy(self.plots))
