#!/usr/bin/env node

/**
 * AgriWise MQTT-to-HTTP Bridge
 * 
 * Subscribes to an MQTT broker and forwards sensor messages 
 * to the AgriWise HTTP ingestion API.
 * 
 * Topic format:
 *   agriwise/sensors/{deviceId}/data    — telemetry payload
 *   agriwise/sensors/{deviceId}/status  — device status (optional)
 * 
 * Message payload (JSON):
 * {
 *   "temperature": 28.5,
 *   "humidity": 65.2,
 *   "soilMoisture": 42.1,
 *   "battery": 87,
 *   "rssi": -55,
 *   "apiKey": "agw_xxx"    // optional, can also be set via --api-key flag
 * }
 * 
 * Usage:
 *   node scripts/mqtt-bridge.js
 *   node scripts/mqtt-bridge.js --broker mqtt://localhost:1883 --topic "agriwise/sensors/+/data"
 *   node scripts/mqtt-bridge.js --broker mqtt://broker.hivemq.com:1883
 * 
 * Environment variables (alternative to flags):
 *   MQTT_BROKER_URL=mqtt://localhost:1883
 *   MQTT_TOPIC=agriwise/sensors/+/data
 *   MQTT_USERNAME=user
 *   MQTT_PASSWORD=pass
 *   AGRIWISE_API_URL=http://localhost:3000
 *   MQTT_DEFAULT_API_KEY=agw_xxx
 */

const mqtt = require("mqtt");

// --- Parse CLI args ---
const args = process.argv.slice(2);
function getArg(name) {
  const idx = args.indexOf(`--${name}`);
  return idx !== -1 && args[idx + 1] ? args[idx + 1] : null;
}

const brokerUrl = getArg("broker") || process.env.MQTT_BROKER_URL || "mqtt://localhost:1883";
const topic = getArg("topic") || process.env.MQTT_TOPIC || "agriwise/sensors/+/data";
const apiUrl = getArg("api-url") || process.env.AGRIWISE_API_URL || "http://localhost:3000";
const mqttUser = getArg("username") || process.env.MQTT_USERNAME || undefined;
const mqttPass = getArg("password") || process.env.MQTT_PASSWORD || undefined;
const defaultApiKey = getArg("api-key") || process.env.MQTT_DEFAULT_API_KEY || undefined;

// --- Stats ---
let messagesReceived = 0;
let messagesForwarded = 0;
let messagesFailed = 0;

// --- Connect to MQTT broker ---
console.log(`\n🔗 AgriWise MQTT Bridge`);
console.log(`   Broker:  ${brokerUrl}`);
console.log(`   Topic:   ${topic}`);
console.log(`   API:     ${apiUrl}/api/sensors/ingest`);
console.log(`   Press Ctrl+C to stop\n`);

const client = mqtt.connect(brokerUrl, {
  username: mqttUser,
  password: mqttPass,
  reconnectPeriod: 5000,
  connectTimeout: 10000,
  clientId: `agriwise-bridge-${Date.now()}`,
});

client.on("connect", () => {
  console.log(`✅ Connected to MQTT broker: ${brokerUrl}`);
  
  client.subscribe(topic, { qos: 1 }, (err, granted) => {
    if (err) {
      console.error(`❌ Subscribe error:`, err.message);
    } else {
      console.log(`📡 Subscribed to: ${granted.map(g => g.topic).join(", ")}\n`);
    }
  });
});

client.on("reconnect", () => {
  console.log(`🔄 Reconnecting to broker...`);
});

client.on("error", (err) => {
  console.error(`❌ MQTT error:`, err.message);
});

client.on("offline", () => {
  console.log(`⚡ Broker connection lost, will retry...`);
});

// --- Handle incoming messages ---
client.on("message", async (receivedTopic, messageBuffer) => {
  messagesReceived++;

  try {
    // Extract deviceId from topic: agriwise/sensors/{deviceId}/data
    const topicParts = receivedTopic.split("/");
    const deviceId = topicParts.length >= 3 ? topicParts[topicParts.length - 2] : null;

    if (!deviceId) {
      console.warn(`⚠️  Could not extract deviceId from topic: ${receivedTopic}`);
      messagesFailed++;
      return;
    }

    // Parse message
    let payload;
    try {
      payload = JSON.parse(messageBuffer.toString());
    } catch {
      console.warn(`⚠️  Invalid JSON from ${receivedTopic}: ${messageBuffer.toString().substring(0, 100)}`);
      messagesFailed++;
      return;
    }

    // Build ingestion body
    const body = {
      deviceId,
      apiKey: payload.apiKey || defaultApiKey || undefined,
      temperature: payload.temperature ?? payload.temp ?? null,
      humidity: payload.humidity ?? payload.hum ?? null,
      soilMoisture: payload.soilMoisture ?? payload.soil ?? payload.moisture ?? null,
      ec: payload.ec ?? null,
      windSpeed: payload.windSpeed ?? payload.wind ?? null,
      rainfall: payload.rainfall ?? payload.rain ?? null,
      battery: payload.battery ?? payload.bat ?? payload.batt ?? null,
      rssi: payload.rssi ?? payload.signal ?? null,
    };

    // Forward to HTTP ingestion API
    const res = await fetch(`${apiUrl}/api/sensors/ingest`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    const data = await res.json();

    if (res.ok) {
      messagesForwarded++;
      const values = [];
      if (body.temperature != null) values.push(`🌡️ ${body.temperature}°C`);
      if (body.humidity != null) values.push(`💧 ${body.humidity}%`);
      if (body.soilMoisture != null) values.push(`🌱 ${body.soilMoisture}%`);
      if (body.battery != null) values.push(`🔋 ${body.battery}%`);

      console.log(
        `✅ #${messagesForwarded} [${deviceId}] ${values.join(" | ")} (${messagesForwarded}/${messagesReceived} ok)`
      );
    } else {
      messagesFailed++;
      console.error(`❌ [${deviceId}] API error: ${data.error} (HTTP ${res.status})`);
    }
  } catch (err) {
    messagesFailed++;
    console.error(`❌ Forward error:`, err.message);
  }
});

// --- Graceful shutdown ---
process.on("SIGINT", () => {
  console.log(`\n📊 Session stats: ${messagesReceived} received, ${messagesForwarded} forwarded, ${messagesFailed} failed`);
  client.end(false, () => {
    console.log("👋 Disconnected from broker");
    process.exit(0);
  });
});

process.on("SIGTERM", () => {
  client.end();
  process.exit(0);
});
