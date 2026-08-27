"""Transition foundations for a future AgriBrain Agricultural World Model.

This package owns the canonical plot worldline, belief snapshot archive,
forecast archive, and event identity. ASMAE (and other layers) consume
and propose events but do NOT own canonical identity or commit authority.

R5.0 establishes the ownership boundary. The existing worldline_service
in layer05_asmae/history/ becomes a one-way delegating adapter.

This package is not the completed Agricultural World Model. It currently
provides canonical worldline, belief, forecast, and event-identity services.
"""
