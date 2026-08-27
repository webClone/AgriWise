from dataclasses import dataclass
from typing import Any, Mapping, Tuple, Union

@dataclass(frozen=True)
class PlotNamespace:
    tenant_id: str
    farm_id: str
    plot_id: str

    def is_valid(self) -> bool:
        return bool(
            self.tenant_id and str(self.tenant_id).strip() and
            self.farm_id and str(self.farm_id).strip() and
            self.plot_id and str(self.plot_id).strip()
        )

    def stable_key(self) -> str:
        return f"{self.tenant_id.strip()}::{self.farm_id.strip()}::{self.plot_id.strip()}"

    def to_tuple(self) -> Tuple[str, str, str]:
        return (self.tenant_id.strip(), self.farm_id.strip(), self.plot_id.strip())

    def __str__(self) -> str:
        return f"{self.tenant_id}:{self.farm_id}:{self.plot_id}"


def _coerce_namespace(
    namespace: Union[PlotNamespace, Mapping[str, Any], str],
    tenant_id: str = "",
    farm_id: str = "",
) -> PlotNamespace:
    if isinstance(namespace, PlotNamespace):
        if not namespace.is_valid():
            raise ValueError(f"Complete PlotNamespace is required: {namespace}")
        return namespace
    if isinstance(namespace, Mapping):
        candidate = PlotNamespace(
            tenant_id=str(namespace.get("tenant_id") or tenant_id or "").strip(),
            farm_id=str(namespace.get("farm_id") or farm_id or "").strip(),
            plot_id=str(namespace.get("plot_id") or "").strip(),
        )
        if not candidate.is_valid():
            raise ValueError(f"Complete PlotNamespace is required: {candidate}")
        return candidate
    p_id = str(namespace).strip() if namespace else ""
    t_id = tenant_id.strip()
    f_id = farm_id.strip()
    if not p_id or not t_id or not f_id:
        raise ValueError("Complete PlotNamespace with non-empty tenant_id, farm_id, and plot_id is required")
    return PlotNamespace(tenant_id=t_id, farm_id=f_id, plot_id=p_id)


def namespace_payload(namespace: PlotNamespace) -> dict[str, str]:
    """Return the canonical JSON-safe durable namespace representation."""
    value = _coerce_namespace(namespace)
    return {
        "tenant_id": value.tenant_id.strip(),
        "farm_id": value.farm_id.strip(),
        "plot_id": value.plot_id.strip(),
    }

