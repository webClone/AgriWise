"""Deep audit of every engine layer data from the live pipeline."""
import requests, json

r = requests.post("http://127.0.0.1:8000/v2/plot-intelligence", json={
    "lat": 36.0, "lng": 3.0,
    "expert_mode": True,
    "days_past": 7, "days_future": 7
})
d = r.json()

print("=" * 65)
print("ENGINE PIPELINE AUDIT — LIVE DATA CHECK")
print("=" * 65)

for eng in d.get("engines", []):
    eid = eng["id"]
    name = eng["name"]
    status = eng["status"]
    label = eng["statusLabel"]
    summary = eng["summary"]
    edata = eng.get("data", {})
    dot = "✅" if status == "OK" else ("⚠️ " if status == "DEGRADED" else "❌")
    print(f"\n{dot} [{eid}] {name}")
    print(f"   Status : {status} — {label}")
    print(f"   Summary: {summary}")
    if edata:
        # Show non-None/non-empty values
        flat = {}
        for k, v in edata.items():
            if isinstance(v, dict):
                for kk, vv in v.items():
                    if vv is not None and vv != {} and vv != []:
                        flat[f"{k}.{kk}"] = vv
            elif v is not None and v != {} and v != []:
                flat[k] = v
        if flat:
            for k, v in list(flat.items())[:8]:
                print(f"   {k}: {v}")
        else:
            print(f"   ⚠️  data dict present but ALL VALUES are None/empty: {list(edata.keys())}")
    else:
        print(f"   ℹ️  No data dict (likely stub engine)")

print("\n" + "=" * 65)
print("CURRENT CONDITIONS SNAPSHOT")
print("=" * 65)
cur = d.get("current", {})
print(f"\n[Weather]  {'PRESENT' if cur.get('weather') else 'MISSING'}")
if cur.get("weather"):
    w = cur["weather"]
    print(f"   temp: {w.get('temperature', {})}")
    print(f"   humidity: {w.get('humidity')}")
    print(f"   wind: {w.get('wind')}")

print(f"\n[Indices]  {'PRESENT' if cur.get('indices') else 'MISSING'}")
if cur.get("indices"):
    idx = cur["indices"]
    print(f"   ndvi={idx.get('ndvi')} evi={idx.get('evi')} ndmi={idx.get('ndmi')} ndwi={idx.get('ndwi')}")

print(f"\n[Soil]     {'PRESENT' if cur.get('soil') else '❌ MISSING/EMPTY'}")
if cur.get("soil"):
    print(f"   {cur['soil']}")
else:
    print("   [soil is falsy — SoilGrids API returning empty dict]")

print(f"\n[WaterBal] {'PRESENT' if cur.get('waterBalance') else 'MISSING'}")
if cur.get("waterBalance"):
    wb = cur["waterBalance"]
    print(f"   et0_today={wb.get('et0_today')} records={len(wb.get('records',[]))}")

print(f"\n[Assimilation]")
a = d.get("assimilation", {})
print(f"   sources_used: {a.get('sources_used')}")
print(f"   freshness: {a.get('freshness_score'):.2f}")

# Quick test SoilGrids directly
print("\n" + "=" * 65)
print("DIRECT SOILGRIDS API TEST")
print("=" * 65)
try:
    sr = requests.get(
        "https://rest.isric.org/soilgrids/v2.0/properties/query",
        params={"lon": 3.0, "lat": 36.0, "property": ["phh2o", "clay", "sand", "soc"], "depth": "0-5cm", "value": "mean"},
        headers={"Accept": "application/json"},
        timeout=15
    )
    print(f"   HTTP {sr.status_code}")
    if sr.status_code == 200:
        sd = sr.json()
        layers = sd.get("properties", {}).get("layers", [])
        print(f"   Layers returned: {len(layers)}")
        for l in layers:
            depths = l.get("depths", [])
            val = depths[0].get("values", {}).get("mean") if depths else None
            print(f"   {l.get('name')}: mean={val} (d_factor={l.get('unit_measure',{}).get('d_factor')})")
    else:
        print(f"   Error: {sr.text[:300]}")
except Exception as e:
    print(f"   Connection error: {e}")
