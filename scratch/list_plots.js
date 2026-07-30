const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

async function main() {
  console.log("Querying all farms...");
  const farms = await prisma.farm.findMany({
    select: { id: true, name: true }
  });
  console.log("Farms in database:", farms);

  console.log("\nQuerying all plots...");
  const plots = await prisma.plot.findMany({
    select: { id: true, name: true, farmId: true }
  });
  console.log("Plots in database:", plots);
}

main()
  .catch((e) => {
    console.error("Error querying db:", e);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
