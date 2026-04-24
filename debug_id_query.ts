import { PrismaClient } from "@prisma/client";

const prisma = new PrismaClient({ log: [] });

async function main() {
  try {
    // 1. Get a valid ID
    const plots = await prisma.plot.findMany({ take: 1 });
    if (plots.length === 0) {
        console.log("No plots available.");
        return;
    }
    const targetId = plots[0].id;
    console.log(`Target ID: '${targetId}'`);

    // 2. Try findFirst with ID
    console.log("--- findFirst({ where: { id: targetId } }) ---");
    const p1 = await prisma.plot.findFirst({
        where: { id: targetId }
    });
    console.log("Result p1:", p1 ? "FOUND" : "NULL");

    // 3. Try findMany with ID
    console.log("--- findMany({ where: { id: targetId } }) ---");
    const p2 = await prisma.plot.findMany({
        where: { id: targetId }
    });
    console.log("Result p2:", p2.length > 0 ? "FOUND" : "EMPTY ARRAY");
    
    // 4. Try findUnique with ID
    console.log("--- findUnique({ where: { id: targetId } }) ---");
    try {
        const p3 = await prisma.plot.findUnique({
            where: { id: targetId }
        });
        console.log("Result p3:", p3 ? "FOUND" : "NULL");
    } catch (e) {
        console.error("findUnique error:", (e as Error).message);
    }

  } catch (e) {
    console.error(e);
  } finally {
    await prisma.$disconnect();
  }
}

main();
