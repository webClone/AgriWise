from typing import Dict, Any
import json
import hmac
import hashlib

def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify HMAC SHA256 signature for incoming webhooks."""
    if not secret:
        return False
    expected_mac = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected_mac, signature)

def parse_http_webhook(payload: bytes, headers: Dict[str, str], secret: str = None) -> Dict[str, Any]:
    """Parse and verify HTTP webhook payload."""
    signature = headers.get("X-Signature", "")
    if secret and not verify_webhook_signature(payload, signature, secret):
        raise ValueError("Invalid webhook signature")
        
    return json.loads(payload.decode('utf-8'))
