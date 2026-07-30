import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import {
  authenticatedUserId,
  userOwnsSensor,
} from "@/lib/tenant-authorization";

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
    const userId = await authenticatedUserId();
    if (!userId) {
      return NextResponse.json(
        { error: "Authentication required" },
        { status: 401 },
      );
    }
    const { id } = await params;
    if (!await userOwnsSensor(userId, id)) {
      return NextResponse.json({ error: "Sensor not found" }, { status: 404 });
    }

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
