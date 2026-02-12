import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";

export async function GET() {
  try {
    // Count farms
    const farmCount = await prisma.farm.count();
    
    // Count plots
    const plotCount = await prisma.plot.count();
    
    // Calculate total area
    const farms = await prisma.farm.findMany({
      select: { totalArea: true }
    });
    const totalArea = farms.reduce((sum, f) => sum + (f.totalArea || 0), 0);
    
    // Count active crop cycles
    const activeCropCount = await prisma.cropCycle.count({
      where: {
        status: {
          in: ["PLANTED", "GROWING", "FLOWERING", "FRUITING"]
        }
      }
    });
    
    // Count upcoming tasks (incomplete tasks due within 7 days)
    const nextWeek = new Date();
    nextWeek.setDate(nextWeek.getDate() + 7);
    
    const upcomingTaskCount = await prisma.cropTask.count({
      where: {
        completed: false,
        dueDate: {
          lte: nextWeek
        }
      }
    });
    
    return NextResponse.json({
      success: true,
      stats: {
        farmCount,
        plotCount,
        totalArea: totalArea.toFixed(1),
        activeCropCount,
        upcomingTaskCount
      }
    });
  } catch (error) {
    console.error("Dashboard stats error:", error);
    return NextResponse.json({
      success: true,
      stats: {
        farmCount: 0,
        plotCount: 0,
        totalArea: "0",
        activeCropCount: 0,
        upcomingTaskCount: 0
      }
    });
  }
}
