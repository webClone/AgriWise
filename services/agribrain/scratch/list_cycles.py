from pymongo import MongoClient
import json
from bson import ObjectId

class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        if hasattr(o, "isoformat"):
            return o.isoformat()
        return super().default(o)

c = MongoClient("mongodb://localhost:27017/agriwise?directConnection=true", serverSelectionTimeoutMS=3000)
db = c["agriwise"]

print("Crop Cycles:")
for doc in db["CropCycle"].find():
    print(json.dumps(doc, indent=2, cls=JSONEncoder))
