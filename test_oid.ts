import { PrismaClient } from '@prisma/client';
import { ObjectId } from 'bson';

const prisma = new PrismaClient();

async function main() {
  const farmId = "699d819a55a7933e54521aac";
  
  try {
    const result1 = await prisma.$runCommandRaw({
      find: "Farm",
      filter: { _id: new ObjectId(farmId) },
      limit: 1
    });
    console.log("Result with new ObjectId:", JSON.stringify(result1, null, 2));
  } catch(e) {
    console.log("Error with new ObjectId:", e);
  }

  try {
    const result2 = await prisma.$runCommandRaw({
      find: "Farm",
      filter: { _id: { $oid: farmId } },
      limit: 1
    });
    console.log("Result with $oid:", JSON.stringify(result2, null, 2));
  } catch(e) {
    console.log("Error with $oid:", e);
  }
}

main().finally(() => prisma.$disconnect());
