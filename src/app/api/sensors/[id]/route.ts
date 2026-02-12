import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";

/**
 * DELETE /api/sensors/[id]
 * 
 * Removes a sensor and all its readings.
 */
export async function DELETE(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;

    // Delete readings first (cascading delete should handle this, but be explicit)
    await prisma.sensorReading.deleteMany({
      where: { sensorId: id },
    });

    await prisma.sensor.delete({
      where: { id },
    });

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error("Delete sensor error:", error);
    return NextResponse.json({ error: "Failed to delete sensor" }, { status: 500 });
  }
}
