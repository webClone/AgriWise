import { ObjectId } from "bson";
import { NextRequest, NextResponse } from "next/server";

import { prisma } from "@/lib/prisma";
import { getSession } from "@/lib/session";

async function ownedPlotId(id: string): Promise<string | null> {
  const session = await getSession();
  if (!session?.userId) return null;
  const plot = await prisma.plot.findFirst({
    where: { id, farm: { userId: session.userId } },
    select: { id: true },
  });
  return plot?.id ?? null;
}

export async function DELETE(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  try {
    const session = await getSession();
    if (!session?.userId) {
      return NextResponse.json(
        { error: "Authentication required" },
        { status: 401 },
      );
    }
    const { id } = await params;
    if (!ObjectId.isValid(id)) {
      return NextResponse.json({ error: "Invalid ID" }, { status: 400 });
    }
    const plotId = await ownedPlotId(id);
    if (!plotId) {
      return NextResponse.json({ error: "Plot not found" }, { status: 404 });
    }
    await prisma.plot.delete({ where: { id: plotId } });
    return NextResponse.json({ success: true });
  } catch (error) {
    console.error("Delete plot error:", error);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  try {
    const session = await getSession();
    if (!session?.userId) {
      return NextResponse.json(
        { error: "Authentication required" },
        { status: 401 },
      );
    }
    const { id } = await params;
    if (!ObjectId.isValid(id)) {
      return NextResponse.json({ error: "Invalid ID" }, { status: 400 });
    }
    const plotId = await ownedPlotId(id);
    if (!plotId) {
      return NextResponse.json({ error: "Plot not found" }, { status: 404 });
    }
    const body = await request.json();
    const { farmId: _farmId, id: _id, createdAt: _createdAt, ...mutable } = body;
    if (mutable.area !== undefined) {
      const area = Number(mutable.area);
      if (!Number.isFinite(area) || area <= 0) {
        return NextResponse.json({ error: "Invalid plot area" }, { status: 400 });
      }
      mutable.area = area;
    }
    const plot = await prisma.plot.update({
      where: { id: plotId },
      data: mutable,
    });
    return NextResponse.json({ success: true, plot });
  } catch (error) {
    console.error("Update plot error:", error);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}
