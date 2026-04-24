import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

async function main() {
  const plot = await prisma.plot.findUnique({
    where: { id: '697dddb0d4195b809226a681' }
  });
  console.log(JSON.stringify(plot, null, 2));
}

main()
  .catch(console.error)
  .finally(() => prisma.$disconnect());
