import sys
try:
    import fastapi
    print("fastapi: OK")
except ImportError:
    print("fastapi: MISSING")

try:
    import uvicorn
    print("uvicorn: OK")
except ImportError:
    print("uvicorn: MISSING")

try:
    import requests
    print("requests: OK")
except ImportError:
    print("requests: MISSING")
    
print(f"Executable: {sys.executable}")
