import { PrismaClient } from '@prisma/client'

const prisma = new PrismaClient()

async function main() {
  const farmId = "699d819a55a7933e54521aac";
  const farm = await prisma.farm.findUnique({
    where: { id: farmId }
  });
  console.log("Farm retrieved using Prisma findUnique:", farm);

  const rawFarm = await prisma.$runCommandRaw({
    find: "Farm",
    filter: { _id: { "$oid": farmId } },
    limit: 1
  });
  console.log("Farm retrieved using runCommandRaw:", JSON.stringify(rawFarm, null, 2));
}

main()
  .catch(console.error)
  .finally(() => prisma.$disconnect());
