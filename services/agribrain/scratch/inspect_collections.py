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

print("Collections and Counts:")
for name in sorted(db.list_collection_names()):
    count = db[name].count_documents({})
    print(f"  {name}: {count} documents")

for col in ["Plot", "CropCycle", "ConfirmedCropLabel"]:
    if col in db.list_collection_names():
        print(f"\n--- Sample from {col} ---")
        doc = db[col].find_one()
        if doc:
            # Print only keys or first 20 lines of JSON to prevent truncation
            js = json.dumps(doc, indent=2, cls=JSONEncoder)
            lines = js.splitlines()
            print("\n".join(lines[:30]))
            if len(lines) > 30:
                print("... (truncated in script) ...")
        else:
            print("No documents found.")
