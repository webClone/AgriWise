from .registry_repository import IPCameraRegistryRepository
from .registry_backends.in_memory import InMemoryCameraRegistry
from .registry_backends.mongo import MongoCameraRegistry

# For backward compatibility during refactor
IPCameraRegistry = InMemoryCameraRegistry
