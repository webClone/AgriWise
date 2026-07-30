import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import {
  authenticatedUserId,
  userOwnsSoilAnalysis,
} from "@/lib/tenant-authorization";

/**
 * DELETE /api/soil-analysis/[id]
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
    if (!await userOwnsSoilAnalysis(userId, id)) {
      return NextResponse.json(
        { error: "Soil analysis not found" },
        { status: 404 },
      );
    }

    await prisma.soilAnalysis.delete({
      where: { id },
    });

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error("Delete soil analysis error:", error);
    return NextResponse.json({ error: "Failed to delete" }, { status: 500 });
  }
}
