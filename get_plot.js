const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

async function main() {
  const plot = await prisma.plot.findUnique({ 
    where: { id: "69fb754f2ab4b04e9f00394c" } 
  });
  console.log("PLOT DATA:", JSON.stringify(plot, null, 2));
}

main()
  .catch(console.error)
  .finally(() => prisma.$disconnect());
