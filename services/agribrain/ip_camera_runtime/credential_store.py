from typing import Optional
from .schemas import IPCameraCredentialsRef

class CredentialStore:
    """
    Stores RTSP credential references and handles tokenized access.
    
    Hard Rule:
    Never expose raw camera passwords to the frontend.
    Never let the browser connect directly to private RTSP cameras.
    """
    
    def __init__(self):
        # mock KMS/vault
        self._secrets = {}
        
    def store_credentials(self, camera_id: str, raw_uri: str) -> IPCameraCredentialsRef:
        """Encrypts and stores raw URI, returns safe reference."""
        secret_id = f"sec_{camera_id}"
        self._secrets[secret_id] = raw_uri  # In reality, this would be encrypted at rest
        return IPCameraCredentialsRef(secret_id=secret_id)
        
    def get_raw_uri(self, ref: IPCameraCredentialsRef) -> Optional[str]:
        """Called ONLY by the backend proxy/relay, NEVER by frontend API."""
        return self._secrets.get(ref.secret_id)
