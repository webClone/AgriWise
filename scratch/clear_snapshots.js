const { PrismaClient } = require("@prisma/client");
const prisma = new PrismaClient();

async function main() {
  console.log("Clearing IntelligenceSnapshot records...");
  const count = await prisma.intelligenceSnapshot.deleteMany({});
  console.log(`Cleared ${count.count} snapshots.`);
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
