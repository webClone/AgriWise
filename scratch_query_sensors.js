const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();
async function main() {
    const sensors = await prisma.sensor.findMany();
    console.log(JSON.stringify(sensors, null, 2));
}
main().catch(console.error).finally(() => prisma.$disconnect());
