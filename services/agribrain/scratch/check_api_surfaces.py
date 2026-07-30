import urllib.request
import json
import base64
from pymongo import MongoClient
from bson import ObjectId

class MongoEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        return super().default(obj)

# 1. Connect to MongoDB and fetch the real plot coordinates/polygon
client = MongoClient("mongodb://localhost:27017/agriwise?directConnection=true")
db = client.agriwise
plot = db.Plot.find_one({"_id": "69de624047f8c01c4979d381"})
if not plot:
    try:
        plot = db.Plot.find_one({"_id": ObjectId("69de624047f8c01c4979d381")})
    except:
        pass

if not plot:
    print("Error: plot 69de624047f8c01c4979d381 not found in MongoDB")
    exit(1)

# Fetch farm for lat/lng
farm = db.Farm.find_one({"_id": plot["farmId"]})
lat = farm["latitude"] if farm else 36.5667
lng = farm["longitude"] if farm else 2.9167

print(f"Plot: {plot.get('name') or plot.get('_id')}")
print(f"Coordinates: lat={lat}, lng={lng}")

context = {
    "plot_id": "69de624047f8c01c4979d381",
    "lat": lat,
    "lng": lng,
    "area": plot.get("area", 12.5),
    "farm_id": str(plot.get("farmId", "UNKNOWN")),
    "polygon": plot.get("geoJson")
}

context_b64 = base64.b64encode(json.dumps(context, cls=MongoEncoder).encode('utf-8')).decode('utf-8')

payload = {
    "context": context_b64,
    "query": "",
    "mode": "surfaces",
    "history": "",
    "exp": "INTERMEDIATE",
    "userMode": "FARMER",
    "force_refresh": True  # Force recalculation to clear cache and use latest real S2 composites
}

url = "http://127.0.0.1:8000/v2/run"
data = json.dumps(payload).encode('utf-8')
req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'}, method='POST')

try:
    print("\nSending POST request to /v2/run...")
    with urllib.request.urlopen(req) as response:
        res_data = json.loads(response.read().decode('utf-8'))
        print("\nSTATUS CODE: 200")
        print(f"RUN ID: {res_data.get('run_id')}")
        
        surfaces = res_data.get('surfaces', [])
        print(f"SURFACES GENERATED: {len(surfaces)}")
        
        # Verify grounding class for each surface
        print("\n--- Surface Grounding Classes ---")
        for s in surfaces:
            s_id = s.get("surface_id")
            s_type = s.get("semantic_type")
            gc = s.get("grounding_class")
            basis = s.get("raster_basis")
            obs_ratio = s.get("observed_ratio")
            print(f"- {s_type} (ID: {s_id}):")
            print(f"  Grounding Class: {gc}")
            print(f"  Raster Basis: {basis}")
            print(f"  Observed Ratio: {obs_ratio}")
            
except Exception as e:
    print(f"REQUEST FAILED: {e}")
