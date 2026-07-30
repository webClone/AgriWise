"""
MongoDB client singleton for AgriBrain.

Provides a single shared MongoClient and database handle.
Avoids per-request MongoClient instantiation which leaks connections
and exhausts the MongoDB connection pool.

Usage:
    from app.mongo_client import get_db
    db = get_db()
    plot = db["Plot"].find_one({"_id": plot_id})
"""

from __future__ import annotations

import os
import logging
from typing import Optional

from pymongo import MongoClient

logger = logging.getLogger("agribrain.mongo")

# Module-level singleton — initialized once on first import
_client: Optional[MongoClient] = None
_db = None


def get_mongo_client() -> MongoClient:
    """Return the shared MongoClient, creating it on first call."""
    global _client
    if _client is None:
        mongo_url = (
            os.environ.get("MONGODB_URI")
            or os.environ.get("DATABASE_URL", "")
        )
        if not mongo_url or "mongodb" not in mongo_url:
            raise RuntimeError(
                "No MongoDB connection string found. "
                "Set MONGODB_URI or DATABASE_URL."
            )
        _client = MongoClient(
            mongo_url,
            serverSelectionTimeoutMS=5000,
            maxPoolSize=10,
            minPoolSize=1,
        )
        logger.info("[MongoDB] Singleton client created (pool=10)")
    return _client


def get_db():
    """Return the shared database handle."""
    global _db
    if _db is None:
        client = get_mongo_client()
        mongo_url = (
            os.environ.get("MONGODB_URI")
            or os.environ.get("DATABASE_URL", "")
        )
        # Extract DB name from connection string
        db_name = "agriwise"
        if "/" in mongo_url:
            candidate = mongo_url.split("/")[-1].split("?")[0]
            if candidate:
                db_name = candidate
        _db = client[db_name]
        logger.info(f"[MongoDB] Using database: {db_name}")
    return _db


def close_mongo():
    """Close the singleton client. Call during shutdown."""
    global _client, _db
    if _client is not None:
        _client.close()
        _client = None
        _db = None
        logger.info("[MongoDB] Singleton client closed")
