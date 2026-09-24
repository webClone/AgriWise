const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

async function main() {
  const farms = await prisma.farm.findMany({ select: { id: true, name: true } });
  console.log('FARMS:', farms);
  const plots = await prisma.plot.findMany({ select: { id: true, name: true, farmId: true } });
  console.log('PLOTS:', plots);
}

main().catch(console.error).finally(() => prisma.$disconnect());
