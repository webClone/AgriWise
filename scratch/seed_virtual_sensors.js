const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

async function main() {
  const plotId = "69de624047f8c01c4979d381";
  
  console.log("Checking plot existence in MongoDB...");
  const plot = await prisma.plot.findUnique({
    where: { id: plotId },
  });

  if (!plot) {
    console.error(`Error: Plot with ID ${plotId} not found in database!`);
    process.exit(1);
  }
  console.log(`Plot found: "${plot.name}". Area: ${plot.area} ha.`);

  // 1. Define 20 virtual sensors with realistic types and device IDs
  const sensorsData = [
    // 10 Soil Moisture Probes (Spatially distributed)
    { deviceId: "AGRI-MOIST-01", type: "MOISTURE", soilMoisture: 16.2, temperature: 24.1, ec: 1.1, battery: 94, rssi: -65 },
    { deviceId: "AGRI-MOIST-02", type: "MOISTURE", soilMoisture: 18.5, temperature: 24.5, ec: 1.2, battery: 89, rssi: -68 },
    { deviceId: "AGRI-MOIST-03", type: "MOISTURE", soilMoisture: 17.8, temperature: 23.9, ec: 0.95, battery: 91, rssi: -71 },
    { deviceId: "AGRI-MOIST-04", type: "MOISTURE", soilMoisture: 20.1, temperature: 25.0, ec: 1.3, battery: 85, rssi: -58 },
    { deviceId: "AGRI-MOIST-05", type: "MOISTURE", soilMoisture: 19.3, temperature: 24.2, ec: 1.15, battery: 95, rssi: -62 },
    { deviceId: "AGRI-MOIST-06", type: "MOISTURE", soilMoisture: 15.8, temperature: 23.7, ec: 1.0, battery: 88, rssi: -75 },
    { deviceId: "AGRI-MOIST-07", type: "MOISTURE", soilMoisture: 17.1, temperature: 24.4, ec: 1.1, battery: 92, rssi: -64 },
    { deviceId: "AGRI-MOIST-08", type: "MOISTURE", soilMoisture: 21.0, temperature: 25.2, ec: 1.4, battery: 87, rssi: -60 },
    { deviceId: "AGRI-MOIST-09", type: "MOISTURE", soilMoisture: 16.9, temperature: 23.8, ec: 1.05, battery: 90, rssi: -72 },
    { deviceId: "AGRI-MOIST-10", type: "MOISTURE", soilMoisture: 18.0, temperature: 24.6, ec: 1.2, battery: 93, rssi: -66 },

    // 4 Soil Temperature Sensors
    { deviceId: "AGRI-TEMP-01", type: "TEMP", soilMoisture: 18.1, temperature: 24.2, battery: 92, rssi: -61 },
    { deviceId: "AGRI-TEMP-02", type: "TEMP", soilMoisture: 17.9, temperature: 24.8, battery: 88, rssi: -67 },
    { deviceId: "AGRI-TEMP-03", type: "TEMP", soilMoisture: 18.4, temperature: 23.9, battery: 94, rssi: -70 },
    { deviceId: "AGRI-TEMP-04", type: "TEMP", soilMoisture: 18.2, temperature: 24.5, battery: 91, rssi: -63 },

    // 4 Electrical Conductivity / Salinity Probes
    { deviceId: "AGRI-EC-01", type: "EC", soilMoisture: 18.0, temperature: 24.0, ec: 1.2, battery: 86, rssi: -69 },
    { deviceId: "AGRI-EC-02", type: "EC", soilMoisture: 17.5, temperature: 24.3, ec: 1.1, battery: 93, rssi: -65 },
    { deviceId: "AGRI-EC-03", type: "EC", soilMoisture: 18.6, temperature: 24.7, ec: 1.35, battery: 89, rssi: -60 },
    { deviceId: "AGRI-EC-04", type: "EC", soilMoisture: 18.2, temperature: 24.1, ec: 1.25, battery: 95, rssi: -62 },

    // 2 Weather Micro-Climate Stations
    { deviceId: "AGRI-WEATH-01", type: "WEATHER", temperature: 27.5, humidity: 44.5, windSpeed: 2.4, rainfall: 0.0, battery: 98, rssi: -52 },
    { deviceId: "AGRI-WEATH-02", type: "WEATHER", temperature: 28.2, humidity: 42.0, windSpeed: 2.9, rainfall: 0.0, battery: 97, rssi: -55 }
  ];

  console.log("Cleaning up old virtual sensors...");
  for (const s of sensorsData) {
    // Delete any existing readings and sensors with matching deviceId to enable re-runs
    const existing = await prisma.sensor.findUnique({
      where: { deviceId: s.deviceId }
    });
    if (existing) {
      await prisma.sensorReading.deleteMany({
        where: { sensorId: existing.id }
      });
      await prisma.sensor.delete({
        where: { id: existing.id }
      });
    }
  }

  console.log("Inserting 20 active virtual sensors and real-time readings...");
  let count = 0;
  for (const s of sensorsData) {
    const sensor = await prisma.sensor.create({
      data: {
        plotId: plotId,
        deviceId: s.deviceId,
        type: s.type,
        status: "ACTIVE",
        battery: s.battery,
        rssi: s.rssi,
        vendor: "AgriBrain Precision",
        lastSync: new Date()
      }
    });

    await prisma.sensorReading.create({
      data: {
        sensorId: sensor.id,
        soilMoisture: s.soilMoisture !== undefined ? Number(s.soilMoisture) : null,
        temperature: s.temperature !== undefined ? Number(s.temperature) : null,
        ec: s.ec !== undefined ? Number(s.ec) : null,
        humidity: s.humidity !== undefined ? Number(s.humidity) : null,
        windSpeed: s.windSpeed !== undefined ? Number(s.windSpeed) : null,
        rainfall: s.rainfall !== undefined ? Number(s.rainfall) : null,
        battery: Number(s.battery),
        rssi: Number(s.rssi),
        timestamp: new Date()
      }
    });
    count++;
  }

  console.log(`Successfully seeded ${count} virtual sensors and readings into plot "${plot.name}"!`);
}

main()
  .catch((e) => {
    console.error("Error seeding sensors:", e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
