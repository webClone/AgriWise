import urllib.request
import json
from pymongo import MongoClient
from bson.objectid import ObjectId

# 1. Check Mongo
client = MongoClient("mongodb://127.0.0.1:27017/agriwise?replicaSet=rs0&directConnection=true")
db = client["agriwise"]
col = db["IntelligenceSnapshot"]
count = col.count_documents({"plotId": ObjectId("69de624047f8c01c4979d381")})
print("Mongo snap count:", count)

# 2. Check FastAPI progress API
try:
    url = "http://127.0.0.1:8000/v2/progress/69de624047f8c01c4979d381"
    res = urllib.request.urlopen(url)
    body = res.read().decode("utf-8")
    parsed = json.loads(body)
    print("FastAPI Progress:", json.dumps(parsed, indent=2))
except Exception as e:
    print("FastAPI progress error:", e)
