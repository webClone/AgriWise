import { PrismaClient } from '@prisma/client'

const prisma = new PrismaClient()

async function main() {
  // 1. Get or create a user
  let user = await prisma.user.findFirst()
  if (!user) {
    user = await prisma.user.create({
      data: {
        name: "Demo User",
        phone: "0000000000",
        wilaya: "Biskra",
        wilayaCode: "07",
        role: "MEDIUM_FARMER"
      }
    })
  }

  // 2. Create the Farm
  const farm = await prisma.farm.create({
    data: {
      name: "Golden Location Farm",
      nameAr: "مزرعة الموقع الذهبي",
      latitude: 34.841, // Biskra region approx
      longitude: 5.728,
      wilaya: "Biskra",
      commune: "Tolga",
      totalArea: 40,
      userId: user.id,
      waterSource: "WELL",
      irrigationType: "DRIP",
      soilType: "SANDY"
    }
  })

  // 3. Create Plots
  const plot1 = await prisma.plot.create({
    data: {
      name: "Golden Plot 1 (Wheat)",
      nameAr: "القطعة الذهبية 1 (قمح)",
      area: 20,
      farmId: farm.id,
      soilType: "SANDY",
      irrigation: "PIVOT"
    }
  })

  const plot2 = await prisma.plot.create({
    data: {
      name: "Golden Plot 2 (Potato)",
      nameAr: "القطعة الذهبية 2 (بطاطا)",
      area: 20,
      farmId: farm.id,
      soilType: "LOAM",
      irrigation: "DRIP"
    }
  })

  // 4. Add Soil Data
  await prisma.soilAnalysis.createMany({
    data: [
      {
        plotId: plot1.id,
        date: new Date(),
        depthFrom: 0,
        depthTo: 30,
        samplingLocation: "Center Zone A",
        ph: 7.2,
        ec: 1.5,
        organicMatter: 1.2,
        nitrogen: 45,
        phosphorus: 20,
        potassium: 150,
        texture: "Sandy Loam"
      },
      {
        plotId: plot2.id,
        date: new Date(),
        depthFrom: 0,
        depthTo: 30,
        samplingLocation: "North West Corner",
        ph: 6.8,
        ec: 1.2,
        organicMatter: 2.1,
        nitrogen: 60,
        phosphorus: 25,
        potassium: 180,
        texture: "Loam"
      }
    ]
  })

  // 5. Add Sensors and Readings
  const sensor1 = await prisma.sensor.create({
    data: {
      plotId: plot1.id,
      type: "MOISTURE",
      deviceId: "SN-GLD-001",
      vendor: "AgriSense",
      status: "ACTIVE",
      battery: 85,
      rssi: -65
    }
  })

  const sensor2 = await prisma.sensor.create({
    data: {
      plotId: plot2.id,
      type: "MOISTURE",
      deviceId: "SN-GLD-002",
      vendor: "AgriSense",
      status: "ACTIVE",
      battery: 92,
      rssi: -50
    }
  })

  const sensor3 = await prisma.sensor.create({
    data: {
      plotId: plot1.id,
      type: "TEMP",
      deviceId: "SN-GLD-003",
      vendor: "AgriSense",
      status: "ACTIVE",
      battery: 78,
      rssi: -72
    }
  })

  // Add readings
  const now = new Date();
  await prisma.sensorReading.createMany({
    data: [
      {
        sensorId: sensor1.id,
        soilMoisture: 22.5,
        temperature: 18.4,
        ec: 1.2,
        battery: 85,
        rssi: -65,
        timestamp: now
      },
      {
        sensorId: sensor1.id,
        soilMoisture: 21.0,
        temperature: 19.1,
        ec: 1.1,
        battery: 86,
        rssi: -66,
        timestamp: new Date(now.getTime() - 3600000) // 1 hour ago
      },
      {
        sensorId: sensor2.id,
        soilMoisture: 28.5,
        temperature: 17.2,
        ec: 1.4,
        battery: 92,
        rssi: -50,
        timestamp: now
      },
      {
        sensorId: sensor3.id,
        temperature: 20.5,
        humidity: 45.2,
        battery: 78,
        rssi: -72,
        timestamp: now
      }
    ]
  })

  console.log("Golden Farm Demo Data Seeded Successfully!")
  console.log("Farm ID:", farm.id)
  console.log("Plot 1 ID:", plot1.id)
  console.log("Plot 2 ID:", plot2.id)
}

main()
  .catch(e => {
    console.error(e)
    process.exit(1)
  })
  .finally(async () => {
    await prisma.$disconnect()
  })
