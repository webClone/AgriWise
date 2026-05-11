const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

async function main() {
  const plotId = "69fb754f2ab4b04e9f00394c";
  const apiKey = "agw_4a3e0d1d8920661ac363b2f7c847f980264006926cfb813c";

  const newSensors = [
    { type: "TEMP", deviceId: "VS-TEMP-01" },
    { type: "WEATHER", deviceId: "VS-WEATHER-01" },
    { type: "EC", deviceId: "VS-EC-01" },
    { type: "MOISTURE", deviceId: "VS-MOISTURE-02" }
  ];

  for (const s of newSensors) {
    await prisma.sensor.upsert({
      where: { deviceId: s.deviceId },
      update: {},
      create: {
        type: s.type,
        deviceId: s.deviceId,
        status: "ACTIVE",
        apiKey,
        plotId
      }
    });
    console.log(`Created ${s.deviceId}`);
  }
}

main().catch(console.error).finally(() => prisma.$disconnect());
