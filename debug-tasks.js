
const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

async function checkLatestCycle() {
  try {
    const cycle = await prisma.cropCycle.findFirst({
      orderBy: { createdAt: 'desc' },
      include: { tasks: true }
    });

    if (!cycle) {
      console.log("No cycles found.");
      return;
    }

    console.log("Latest Cycle:", {
        id: cycle.id,
        crop: cycle.cropNameAr,
        status: cycle.status,
        createdAt: cycle.createdAt,
        notes: cycle.notes
    });
    console.log(`Task Count: ${cycle.tasks.length}`);
    if (cycle.tasks.length > 0) {
        console.log("Sample Task:", cycle.tasks[0]);
    } else {
        console.log("No tasks linked to this cycle.");
    }
  } catch (e) {
    console.error(e);
  } finally {
    await prisma.$disconnect();
  }
}

checkLatestCycle();
