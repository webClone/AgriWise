"""
Deterministic identity mapping and hashing helper methods.
"""
import hashlib

def generate_transform_hash(transform: list) -> str:
    hasher = hashlib.sha256()
    hasher.update(str(transform).encode("utf-8"))
    return hasher.hexdigest()

def generate_footprint_hash(footprint_coords: str) -> str:
    hasher = hashlib.sha256()
    hasher.update(str(footprint_coords).encode("utf-8"))
    return hasher.hexdigest()
