#!/usr/bin/env node

/**
 * MQTT Sensor Simulator — publishes fake telemetry to an MQTT broker.
 * Use with the MQTT bridge to test the full MQTT pipeline.
 * 
 * Usage:
 *   node scripts/simulate-sensor-mqtt.js --device-id ESP32-FIELD-A1
 *   node scripts/simulate-sensor-mqtt.js --device-id ESP32-FIELD-A1 --broker mqtt://localhost:1883 --interval 10
 * 
 * Options:
 *   --device-id   Device ID (required)
 *   --broker      MQTT broker URL (default: mqtt://localhost:1883)
 *   --interval    Seconds between readings (default: 10)
 *   --type        Sensor type: moisture, temp, weather, ec (default: temp)
 *   --api-key     API key to include in payload (optional)
 */

const mqtt = require("mqtt");

const args = process.argv.slice(2);
function getArg(name) {
  const idx = args.indexOf(`--${name}`);
  return idx !== -1 && args[idx + 1] ? args[idx + 1] : null;
}

const deviceId = getArg("device-id");
const brokerUrl = getArg("broker") || "mqtt://localhost:1883";
const interval = parseInt(getArg("interval") || "10");
const sensorType = (getArg("type") || "temp").toLowerCase();
const apiKey = getArg("api-key") || undefined;

if (!deviceId) {
  console.error("❌ Usage: node simulate-sensor-mqtt.js --device-id DEV-1234");
  process.exit(1);
}

const topic = `agriwise/sensors/${deviceId}/data`;

let battery = 95 + Math.random() * 5;
let baseTemp = 20 + Math.random() * 10;
let baseHumidity = 50 + Math.random() * 20;
let baseSoilMoisture = 30 + Math.random() * 30;
let baseEc = 0.5 + Math.random() * 1.5;
let readingCount = 0;

function generateReading() {
  readingCount++;
  battery = Math.max(0, battery - (0.01 + Math.random() * 0.02));
  const rssi = -40 - Math.floor(Math.random() * 40);

  baseTemp += (Math.random() - 0.5) * 0.3;
  baseHumidity += (Math.random() - 0.5) * 1;
  baseSoilMoisture += (Math.random() - 0.5) * 0.8;
  baseEc += (Math.random() - 0.5) * 0.05;

  baseTemp = Math.max(10, Math.min(45, baseTemp));
  baseHumidity = Math.max(20, Math.min(95, baseHumidity));
  baseSoilMoisture = Math.max(5, Math.min(90, baseSoilMoisture));
  baseEc = Math.max(0.1, Math.min(4, baseEc));

  const payload = { battery: parseFloat(battery.toFixed(1)), rssi };
  if (apiKey) payload.apiKey = apiKey;

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

console.log(`\n🚀 MQTT Sensor Simulator`);
console.log(`   Device:   ${deviceId}`);
console.log(`   Topic:    ${topic}`);
console.log(`   Broker:   ${brokerUrl}`);
console.log(`   Type:     ${sensorType}`);
console.log(`   Interval: ${interval}s\n`);

const client = mqtt.connect(brokerUrl);

client.on("connect", () => {
  console.log(`✅ Connected to broker\n`);

  // Send first reading immediately
  publish();
  setInterval(publish, interval * 1000);
});

client.on("error", (err) => {
  console.error(`❌ MQTT error: ${err.message}`);
});

function publish() {
  const reading = generateReading();
  const msg = JSON.stringify(reading);

  client.publish(topic, msg, { qos: 1 }, (err) => {
    if (err) {
      console.error(`❌ #${readingCount} Publish error: ${err.message}`);
    } else {
      const values = [];
      if (reading.temperature != null) values.push(`🌡️ ${reading.temperature}°C`);
      if (reading.humidity != null) values.push(`💧 ${reading.humidity}%`);
      if (reading.soilMoisture != null) values.push(`🌱 ${reading.soilMoisture}%`);
      values.push(`🔋 ${reading.battery}%`);
      values.push(`📶 ${reading.rssi} dBm`);

      console.log(`📤 #${readingCount} → ${topic} | ${values.join(" | ")}`);
    }
  });
}

process.on("SIGINT", () => {
  console.log(`\n📊 Published ${readingCount} readings`);
  client.end(false, () => {
    console.log("👋 Disconnected");
    process.exit(0);
  });
});
