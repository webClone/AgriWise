from datetime import datetime, timedelta, timezone
import uuid
from typing import Optional

from .schemas import StreamSession
from .credential_store import CredentialStore

class StreamProxy:
    """
    Backend proxy / relay integration.
    Wraps MediaMTX/ffmpeg interactions.
    """
    
    def __init__(self, credential_store: CredentialStore):
        self.credential_store = credential_store
        self.active_sessions = {}
        
    def create_session(self, camera_id: str, secret_id: str) -> Optional[StreamSession]:
        """
        Creates a temporary HLS/WebRTC proxy session for a camera.
        Frontend uses the proxy_url, not the RTSP.
        """
        # In reality, this would spin up a MediaMTX route
        session_id = str(uuid.uuid4())
        proxy_url = f"https://api.agriwise.local/stream/{session_id}/index.m3u8"
        
        session = StreamSession(
            session_id=session_id,
            camera_id=camera_id,
            started_at=datetime.now(tz=timezone.utc),
            proxy_url=proxy_url,
            expires_at=datetime.now(tz=timezone.utc) + timedelta(hours=1)
        )
        self.active_sessions[session_id] = session
        return session
