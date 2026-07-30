import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { authenticatedUserId } from "@/lib/tenant-authorization";

export async function GET() {
  try {
    const userId = await authenticatedUserId();
    if (!userId) {
      return NextResponse.json(
        { error: "Authentication required" },
        { status: 401 },
      );
    }
    const farmCount = await prisma.farm.count({ where: { userId } });
    
    // Count plots
    const plotCount = await prisma.plot.count({
      where: { farm: { userId } },
    });
    
    // Calculate total area
    const farms = await prisma.farm.findMany({
      where: { userId },
      select: { totalArea: true }
    });
    const totalArea = farms.reduce((sum, f) => sum + (f.totalArea || 0), 0);
    
    // Count active crop cycles
    const activeCropCount = await prisma.cropCycle.count({
      where: {
        plot: { farm: { userId } },
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
        cropCycle: { plot: { farm: { userId } } },
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
