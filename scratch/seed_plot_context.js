const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

async function main() {
  const plotId = "69de624047f8c01c4979d381";
  
  console.log("Locating plot in database...");
  const plot = await prisma.plot.findUnique({
    where: { id: plotId }
  });

  if (!plot) {
    console.error("Plot not found!");
    process.exit(1);
  }

  // 1. Delete any existing empty/broken crop cycles for a clean run
  console.log("Cleaning up old crop cycle records...");
  await prisma.cropCycle.deleteMany({
    where: { plotId: plotId }
  });

  // 2. Create an active growing CropCycle (Tomato variety 'Marmande')
  // Planted 14 days ago, putting it exactly in the EMERGENCE/EARLY VEGETATIVE stage
  const plantDate = new Date();
  plantDate.setDate(plantDate.getDate() - 14);

  const expectedHarvest = new Date(plantDate);
  expectedHarvest.setDate(expectedHarvest.getDate() + 110); // 110-day cycle

  console.log("Creating active CropCycle for Tomato (Emergence stage)...");
  const cycle = await prisma.cropCycle.create({
    data: {
      plotId: plotId,
      cropCode: "tomato",
      cropNameAr: "طماطم",
      variety: "Marmande",
      plantDate: plantDate,
      expectedHarvest: expectedHarvest,
      status: "GROWING",
      estimatedYield: 35000, // 35 tons/ha expected
      notes: "Emergence monitoring enabled with IoT probes."
    }
  });
  console.log("CropCycle seeded successfully:", cycle.id);

  // 3. Delete any existing soil analysis records for a clean run
  console.log("Cleaning up old soil analysis records...");
  await prisma.soilAnalysis.deleteMany({
    where: { plotId: plotId }
  });

  // 4. Create a comprehensive SoilAnalysis record
  console.log("Creating SoilAnalysis record (pH, EC, organic matter, clay)...");
  const soil = await prisma.soilAnalysis.create({
    data: {
      plotId: plotId,
      date: new Date(),
      ph: 6.5,
      ec: 1.2, // dS/m
      organicMatter: 2.8, // %
      nitrogen: 45.0, // ppm
      phosphorus: 18.5, // ppm
      potassium: 160.0, // ppm
      texture: "Clay",
      samplingLocation: "GPS Center Grid Zone",
      notes: "Baseline sampling for irrigation scheduling."
    }
  });
  console.log("SoilAnalysis seeded successfully:", soil.id);
  console.log("\nComplete! All physical context elements are now in place.");
}

main()
  .catch((e) => {
    console.error("Error seeding context:", e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
