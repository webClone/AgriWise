from typing import Dict, List, Optional
import json
from dataclasses import asdict
from datetime import datetime
from ..schemas import (
    IPCameraRegistration,
    CameraProtocol,
    CameraType,
    CameraViewConfig,
    IPCameraCredentialsRef,
    FrameCapturePolicy,
)
from ..registry_repository import IPCameraRegistryRepository


def _registration_to_doc(config: IPCameraRegistration) -> dict:
    """Serialize an IPCameraRegistration dataclass to a MongoDB document."""
    doc = asdict(config)
    # Convert enums to their string values for MongoDB storage
    doc["protocol"] = config.protocol.value
    doc["camera_type"] = config.camera_type.value
    # Convert datetime to ISO string (MongoDB handles datetime natively,
    # but ISO strings are more portable)
    if doc.get("last_frame_received_at") and isinstance(config.last_frame_received_at, datetime):
        doc["last_frame_received_at"] = config.last_frame_received_at.isoformat()
    return doc


def _doc_to_registration(doc: dict) -> IPCameraRegistration:
    """Deserialize a MongoDB document to an IPCameraRegistration dataclass."""
    # Reconstruct nested dataclasses
    view_config = CameraViewConfig(**doc.get("view_config", {})) if doc.get("view_config") else CameraViewConfig()

    creds_ref = None
    if doc.get("credentials_ref"):
        creds_ref = IPCameraCredentialsRef(**doc["credentials_ref"])

    capture_policy = FrameCapturePolicy(**doc.get("capture_policy", {})) if doc.get("capture_policy") else FrameCapturePolicy()

    # Parse datetime
    last_frame = doc.get("last_frame_received_at")
    if isinstance(last_frame, str):
        try:
            last_frame = datetime.fromisoformat(last_frame)
        except (ValueError, TypeError):
            last_frame = None

    return IPCameraRegistration(
        camera_id=doc["camera_id"],
        plot_id=doc["plot_id"],
        protocol=CameraProtocol(doc.get("protocol", "rtsp")),
        camera_type=CameraType(doc.get("camera_type", "fixed")),
        is_primary_validation_camera=doc.get("is_primary_validation_camera", True),
        view_config=view_config,
        credentials_ref=creds_ref,
        capture_policy=capture_policy,
        online_status=doc.get("online_status", "offline"),
        last_frame_received_at=last_frame,
    )


class MongoCameraRegistry(IPCameraRegistryRepository):
    """
    MongoDB storage backend for IPCameraRegistry.
    Used for production to persist camera configurations across restarts.
    """

    def __init__(self, collection):
        """
        Expects a pymongo Collection object.
        """
        self.collection = collection

        # Ensure index on camera_id for fast lookups
        self.collection.create_index("camera_id", unique=True)
        self.collection.create_index("plot_id")

    def register_camera(self, config: IPCameraRegistration) -> None:
        doc = _registration_to_doc(config)
        self.collection.replace_one(
            {"camera_id": config.camera_id},
            doc,
            upsert=True
        )

    def get_camera(self, camera_id: str) -> Optional[IPCameraRegistration]:
        doc = self.collection.find_one({"camera_id": camera_id})
        if not doc:
            return None
        # Remove the internal mongo _id before parsing
        doc.pop("_id", None)
        return _doc_to_registration(doc)

    def get_cameras_for_plot(self, plot_id: str) -> List[IPCameraRegistration]:
        cursor = self.collection.find({"plot_id": plot_id})
        cameras = []
        for doc in cursor:
            doc.pop("_id", None)
            cameras.append(_doc_to_registration(doc))
        return cameras

    def list_all(self) -> List[IPCameraRegistration]:
        """Return all registered cameras."""
        cameras = []
        for doc in self.collection.find({}):
            doc.pop("_id", None)
            cameras.append(_doc_to_registration(doc))
        return cameras

