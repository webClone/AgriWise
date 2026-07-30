from pymongo import MongoClient
from bson.objectid import ObjectId

client = MongoClient("mongodb://127.0.0.1:27017/agriwise?replicaSet=rs0&directConnection=true")
db = client["agriwise"]
col = db["IntelligenceSnapshot"]

plot_id_obj = ObjectId("69de624047f8c01c4979d381")
result = col.delete_many({"plotId": plot_id_obj})
print(f"Deleted {result.deleted_count} snapshots for plot 69de624047f8c01c4979d381")
