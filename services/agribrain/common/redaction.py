def redact_api_key(key: str) -> str:
    """Safely redact API keys without exposing prefix or suffix."""
    if not key:
        return "NOT_FOUND"
    return "<LOADED>"

def redact_secrets(data: dict) -> dict:
    """
    Recursively redacts common secret keys (e.g., api_key, token, password, secret) in a dictionary.
    """
    if not isinstance(data, dict):
        return data
    redacted = {}
    secret_keywords = {"api_key", "token", "password", "secret", "private_key", "appid"}
    for k, v in data.items():
        if isinstance(v, dict):
            redacted[k] = redact_secrets(v)
        elif isinstance(v, str) and any(kw in k.lower() for kw in secret_keywords):
            redacted[k] = redact_api_key(v)
        else:
            redacted[k] = v
    return redacted
