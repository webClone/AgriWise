import { prisma } from '../src/lib/db';

async function main() {
  try {
    const plot = await prisma.plot.findFirst({
      include: { cropCycles: true }
    });
    if (plot) {
      console.log("PLOT_ID:", plot.id);
      console.log("CROP:", plot.cropCycles[0]?.cropCode);
    } else {
      console.log("NO_PLOTS_FOUND");
    }
  } catch (e) {
    console.error(e);
  } finally {
    await prisma.$disconnect();
  }
}

main();
