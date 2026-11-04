"""B2B-05 request-scoped, verified identity handoff to Layer 0.

Only the existing signed internal-service dependency authenticates the
namespace. Header values, body fields and dev fallback are never themselves
a trusted principal. Every context token is reset after the request.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from collections.abc import Iterator
from typing import Optional

from fastapi import Depends, Request

from services.agribrain.app.internal_service_auth import require_internal_service_request
from services.agribrain.common.plot_namespace import PlotNamespace
from services.agribrain.layer0.spatial_tenant_contract import (
    AuthenticatedPrincipal, SpatialTenantDenied,
)

_current_scoped_principal: ContextVar[Optional[AuthenticatedPrincipal]] = ContextVar(
    "akaloris_b2b05_authenticated_principal", default=None,
)


def current_authenticated_plot_principal() -> AuthenticatedPrincipal:
    """Trusted provider callable installed on broker at application startup."""
    identity = _current_scoped_principal.get()
    if not isinstance(identity, AuthenticatedPrincipal) or identity.authenticated is not True:
        raise SpatialTenantDenied("authenticated_plot_principal_required")
    return identity


@contextmanager
def bind_authenticated_plot_namespace(
    namespace: PlotNamespace, *, signature_verified: bool,
) -> Iterator[None]:
    """Bind only a completed signed-auth dependency result, never raw headers.

    Used by the FastAPI dependency and by controlled unit tests. The caller
    is responsible for establishing a valid internal request signature.
    """
    if not isinstance(namespace, PlotNamespace):
        raise SpatialTenantDenied("invalid_authenticated_plot_namespace")
    principal = (
        AuthenticatedPrincipal(
            tenant_id=namespace.tenant_id,
            subject_id="internal-service:" + namespace.farm_id,
            authenticated=True,
        )
        if signature_verified else None
    )
    token = _current_scoped_principal.set(principal)
    try:
        yield
    finally:
        _current_scoped_principal.reset(token)


async def require_b2b05_internal_request(
    request: Request,
    namespace: PlotNamespace = Depends(require_internal_service_request),
):
    """Existing authentication first; then scoped identity for this request.

    Unsigned opt-in local development sessions keep legacy endpoint access,
    but never obtain authenticated plot ownership authority.
    """
    signed = bool(request.headers.get("X-AgriBrain-Signature"))
    with bind_authenticated_plot_namespace(namespace, signature_verified=signed):
        yield namespace
