"""
AgriBrain Data Gateway — Centralized data ingestion for Layer 0.

The DataRequestBroker is the SINGLE entry point for ALL data requests
across ALL layers. No layer, engine, or runtime may fetch data
independently — everything flows through here.

Usage from any layer:
    from layer0.data_gateway import broker

    # EO data
    soil = broker.get("soilgrids", plot_id="abc", lat=33.5, lng=-7.6)

    # Bulk fetch (parallel, consolidated)
    data = broker.get_bulk(["openweather_current", "sentinel2_indices", "soilgrids"],
                           plot_id="abc", lat=33.5, lng=-7.6)

    # Freshness check (no fetch)
    status = broker.freshness(plot_id="abc")

    # Confidence score (ML Pattern 6)
    conf = broker.confidence("soilgrids", plot_id="abc")
"""

# Lazy singleton — initialized on first import of broker
_broker_instance = None


def get_broker():
    """Get or create the singleton DataRequestBroker."""
    global _broker_instance
    if _broker_instance is None:
        from layer0.data_gateway.request_broker import DataRequestBroker
        _broker_instance = DataRequestBroker()
    return _broker_instance


class _BrokerProxy:
    """Lazy proxy that forwards all attribute access to the real broker.

    This allows `from layer0.data_gateway import broker` to work at
    import time without triggering MongoDB connections or heavy init.
    """

    def __getattr__(self, name):
        return getattr(get_broker(), name)

    def __repr__(self):
        return f"<BrokerProxy → {get_broker().__class__.__name__}>"


broker = _BrokerProxy()
