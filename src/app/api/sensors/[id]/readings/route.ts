import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";

/**
 * GET /api/sensors/[id]/readings?limit=50
 * 
 * Returns recent readings for a specific sensor.
 */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const { searchParams } = new URL(request.url);
    const limit = Math.min(parseInt(searchParams.get("limit") || "50"), 200);

    const readings = await prisma.sensorReading.findMany({
      where: { sensorId: id },
      orderBy: { timestamp: "desc" },
      take: limit,
    });

    return NextResponse.json({ readings });
  } catch (error) {
    console.error("Sensor readings error:", error);
    return NextResponse.json({ error: "Failed to fetch readings" }, { status: 500 });
  }
}
