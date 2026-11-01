"""Joined-clock fixture: run native acquisition adapter and native Mongo promoter
with in-memory HTTP/collection adapters; no external provider/database calls.
Called by tests/frontend/operational-weather-clock.test.mjs.
"""
import ast
import json
import sys
import types
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

ROOT = Path(__file__).resolve().parents[2]
WEATHER = ROOT / "services/agribrain/eo/weather.py"
PROMOTER = ROOT / "services/agribrain/eo/observation_promoter.py"

# Use the actual provider functions, without initializing EO/network subsystems.
tree = ast.parse(WEATHER.read_text(encoding="utf-8"))
functions = [
    node for node in tree.body
    if isinstance(node, ast.FunctionDef)
    and node.name in ("fetch_openweather_data", "_fetch_open_meteo_weather")
]
assert len(functions) == 2
ns = {"datetime": datetime, "timezone": timezone, "Dict": Dict, "Optional": Optional}
ns["os"] = types.SimpleNamespace(getenv=lambda key: "fixture-not-real-secret")
ns["EO_REQUEST_TIMEOUT"] = 2
ns["_fetch_open_meteo_weather"] = lambda lat, lng: None
mod = types.ModuleType("common")
redaction = types.ModuleType("common.redaction")
redaction.redact_api_key = lambda value: "[REDACTED]"
sys.modules["common"] = mod
sys.modules["common.redaction"] = redaction

response_data = {}
class HTTPResponse:
    def __init__(self, payload, status=200):
        self.payload, self.status_code = payload, status
    def json(self):
        return self.payload
    text = ""
def fetch(url, **kwargs):
    if url.endswith("/uvi"):
        return HTTPResponse({}, 404)
    return HTTPResponse(response_data["value"])
ns["requests"] = types.SimpleNamespace(get=fetch)
exec(compile(ast.Module(body=functions, type_ignores=[]), str(WEATHER), "exec"), ns)

promoter_ns = {}
exec(compile(PROMOTER.read_text(encoding="utf-8"), str(PROMOTER), "exec"), promoter_ns)
sys.modules["bson"] = types.SimpleNamespace(ObjectId=lambda value: value)

class MongoCollection:
    def __init__(self):
        self.rows = []
    def update_one(self, filt, update, upsert=False):
        if "$setOnInsert" in update:
            self.rows.append(update["$setOnInsert"])
        return types.SimpleNamespace(upserted_id="fixture-new")
class Counts:
    def update_one(self, *args, **kwargs):
        return None
def promote(case, epoch):
    raw = {
        "main": {"temp": 0, "humidity": 70},
        "weather": [{"main": "Clear"}], "wind": {}, "clouds": {},
    }
    if epoch is not None:
        raw["dt"] = epoch
    response_data["value"] = raw
    adapter = ns["fetch_openweather_data"](36.6, 3.0)
    assert isinstance(adapter, dict)
    writer = types.SimpleNamespace(PlotObservation=MongoCollection(), PlotDNA=Counts())
    fetched = datetime(2026, 10, 31, 14, 1, tzinfo=timezone.utc)
    assert promoter_ns["promote_to_observation"](
        writer, "507f1f77bcf86cd799439011", "openweather_current",
        36.6, 3.0, adapter, fetched_at=fetched
    )
    row = writer.PlotObservation.rows[0]
    return {
        "id": "weather-" + case,
        "source": row["source"],
        "obsType": row["obsType"],
        "obsDate": row["obsDate"].isoformat(),
        "fetchedAt": row["fetchedAt"].isoformat(),
        "data": row["data"],
        "tempC": row["tempC"],
        "humidity": row["humidity"],
    }

late_epoch = int(datetime(2026, 10, 31, 9, 0, tzinfo=timezone.utc).timestamp())
live_epoch = int(datetime(2026, 10, 31, 14, 0, tzinfo=timezone.utc).timestamp())
rows = {
    "live": promote("live", live_epoch),
    "late": promote("late", late_epoch),
    "legacy": promote("legacy", None),
}

# Open-Meteo UTC provider clock is also preserved if it is qualified.
response_data["value"] = {
    "current": {
        "time": "2026-10-31T14:00",
        "temperature_2m": 0,
        "relative_humidity_2m": 70,
        "weather_code": 0,
    },
    "utc_offset_seconds": 0,
}
meteo = ns["_fetch_open_meteo_weather"](36.6, 3.0)
assert meteo["observed_at"] == "2026-10-31T14:00:00+00:00", meteo

print("__CLOCK_JSON__" + json.dumps({
    "rows": rows,
    "cutoff": "2026-10-31T10:00:00Z",
    "now": "2026-10-31T15:00:00Z",
    "openMeteoAcquired": meteo["observed_at"],
}))
