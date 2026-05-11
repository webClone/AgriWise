/**
 * Register 5 sensors on the active plot and launch simulators.
 */
const PLOT_ID = "69de624047f0c01c4979d381";
const BASE = "http://localhost:3000";

const SENSORS = [
  { deviceId: "FLD-MOISTURE-01", type: "MOISTURE", vendor: "Capacitive-v2" },
  { deviceId: "FLD-MOISTURE-02", type: "MOISTURE", vendor: "Capacitive-v2" },
  { deviceId: "FLD-TEMP-01",     type: "TEMP",     vendor: "DS18B20" },
  { deviceId: "FLD-WEATHER-01",  type: "WEATHER",  vendor: "Davis-VP2" },
  { deviceId: "FLD-EC-01",       type: "EC",       vendor: "Teros-12" },
];

async function registerAll() {
  const results = [];
  for (const s of SENSORS) {
    const res = await fetch(`${BASE}/api/sensors/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ plotId: PLOT_ID, ...s }),
    });
    const data = await res.json();
    if (res.ok) {
      console.log(`✅ Registered ${s.deviceId} → apiKey: ${data.apiKey}`);
      results.push({ ...s, apiKey: data.apiKey });
    } else {
      console.log(`⚠️  ${s.deviceId}: ${data.error}`);
      // If already registered, try to find existing apiKey
      if (res.status === 409) {
        results.push({ ...s, apiKey: null, existing: true });
      }
    }
  }
  return results;
}

registerAll().then(r => {
  console.log("\n📋 Registration complete. Sensors:");
  console.log(JSON.stringify(r, null, 2));
});
