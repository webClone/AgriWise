from pymongo import MongoClient

client = MongoClient("mongodb://127.0.0.1:27017/agriwise?replicaSet=rs0&directConnection=true")
db = client["agriwise"]
col = db["IntelligenceSnapshot"]
doc = col.find_one()
if doc:
    # Print keys and types, or omit binary grids to keep clean
    for k, v in doc.items():
        if k == "surfaceGridsGz":
            print(k, "-> <binary bytes>")
        else:
            print(k, "->", type(v), repr(v)[:100])
else:
    print("No snapshots found in IntelligenceSnapshot")
