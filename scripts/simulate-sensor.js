#!/usr/bin/env node

/**
 * Sensor Simulator — sends fake telemetry to the AgriWise ingestion API.
 * 
 * Usage:
 *   node scripts/simulate-sensor.js --device-id YOUR_DEVICE_ID --api-key YOUR_API_KEY
 *   node scripts/simulate-sensor.js --device-id ESP32-FIELD-A1 --api-key agw_abc123 --interval 10
 * 
 * Options:
 *   --device-id   Device ID registered in AgriWise (required)
 *   --api-key     API key from registration (required)
 *   --interval    Seconds between readings (default: 10)
 *   --url         Server URL (default: http://localhost:3000)
 *   --type        Sensor type: moisture, temp, weather, ec (default: temp)
 */

const args = process.argv.slice(2);

function getArg(name) {
  const idx = args.indexOf(`--${name}`);
  return idx !== -1 && args[idx + 1] ? args[idx + 1] : null;
}

const deviceId = getArg("device-id");
const apiKey = getArg("api-key");
const interval = parseInt(getArg("interval") || "10");
const baseUrl = getArg("url") || "http://localhost:3000";
const sensorType = (getArg("type") || "temp").toLowerCase();

if (!deviceId || !apiKey) {
  console.error("❌ Usage: node simulate-sensor.js --device-id DEV-1234 --api-key agw_xxx");
  process.exit(1);
}

// State that changes slowly over time
let battery = 95 + Math.random() * 5; // Start near 100%
let baseTemp = 20 + Math.random() * 10;
let baseHumidity = 50 + Math.random() * 20;
let baseSoilMoisture = 30 + Math.random() * 30;
let baseEc = 0.5 + Math.random() * 1.5;
let readingCount = 0;

function generateReading() {
  readingCount++;

  // Battery slowly drains
  battery = Math.max(0, battery - (0.01 + Math.random() * 0.02));

  // RSSI fluctuates around a base
  const rssi = -40 - Math.floor(Math.random() * 40); // -40 to -80 dBm

  // Values drift slowly with noise
  baseTemp += (Math.random() - 0.5) * 0.3;
  baseHumidity += (Math.random() - 0.5) * 1;
  baseSoilMoisture += (Math.random() - 0.5) * 0.8;
  baseEc += (Math.random() - 0.5) * 0.05;

  // Clamp values
  baseTemp = Math.max(10, Math.min(45, baseTemp));
  baseHumidity = Math.max(20, Math.min(95, baseHumidity));
  baseSoilMoisture = Math.max(5, Math.min(90, baseSoilMoisture));
  baseEc = Math.max(0.1, Math.min(4, baseEc));

  const payload = {
    deviceId,
    apiKey,
    battery: parseFloat(battery.toFixed(1)),
    rssi,
  };

  // Add fields based on sensor type
  if (sensorType === "temp" || sensorType === "weather") {
    payload.temperature = parseFloat(baseTemp.toFixed(1));
    payload.humidity = parseFloat(baseHumidity.toFixed(1));
  }
  if (sensorType === "moisture" || sensorType === "weather") {
    payload.soilMoisture = parseFloat(baseSoilMoisture.toFixed(1));
  }
  if (sensorType === "ec") {
    payload.ec = parseFloat(baseEc.toFixed(2));
  }
  if (sensorType === "weather") {
    payload.windSpeed = parseFloat((Math.random() * 25).toFixed(1));
    payload.rainfall = parseFloat((Math.random() * 2).toFixed(1));
  }

  return payload;
}

async function sendReading() {
  const reading = generateReading();
  
  try {
    const res = await fetch(`${baseUrl}/api/sensors/ingest`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(reading),
    });

    const data = await res.json();

    if (res.ok) {
      const values = [];
      if (reading.temperature != null) values.push(`🌡️ ${reading.temperature}°C`);
      if (reading.humidity != null) values.push(`💧 ${reading.humidity}%`);
      if (reading.soilMoisture != null) values.push(`🌱 ${reading.soilMoisture}%`);
      if (reading.ec != null) values.push(`⚡ ${reading.ec} mS/cm`);
      if (reading.windSpeed != null) values.push(`🌬️ ${reading.windSpeed} km/h`);
      if (reading.rainfall != null) values.push(`🌧️ ${reading.rainfall} mm`);

      console.log(
        `✅ #${readingCount} | ${values.join(" | ")} | 🔋 ${reading.battery}% | 📶 ${reading.rssi} dBm`
      );
    } else {
      console.error(`❌ #${readingCount} | Error: ${data.error}`);
    }
  } catch (err) {
    console.error(`❌ #${readingCount} | Network error: ${err.message}`);
  }
}

console.log(`\n🚀 AgriWise Sensor Simulator`);
console.log(`   Device:   ${deviceId}`);
console.log(`   Type:     ${sensorType}`);
console.log(`   Interval: ${interval}s`);
console.log(`   Server:   ${baseUrl}`);
console.log(`   Press Ctrl+C to stop\n`);

// Send first reading immediately
sendReading();

// Then at intervals
setInterval(sendReading, interval * 1000);
