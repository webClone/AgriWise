import { ObjectId } from "bson";
import { NextRequest, NextResponse } from "next/server";

import { prisma } from "@/lib/prisma";
import { getSession } from "@/lib/session";
import { updatePlotGeometry } from "@/lib/agribrain/plot-geometry-epoch";

async function ownedPlot(id: string) {
  const session = await getSession();
  if (!session?.userId) return null;
  const plot = await prisma.plot.findFirst({
    where: { id, farm: { userId: session.userId } },
    select: {
      id: true, farmId: true, geometryVersion: true,
      geometryHash: true, geoJson: true,
    },
  });
  return plot;
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
    const currentPlot = await ownedPlot(id);
    if (!currentPlot) {
      return NextResponse.json({ error: "Plot not found" }, { status: 404 });
    }
    await prisma.plot.delete({ where: { id: currentPlot.id } });
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
    const currentPlot = await ownedPlot(id);
    if (!currentPlot) {
      return NextResponse.json({ error: "Plot not found" }, { status: 404 });
    }
    const body = await request.json();
    const {
      farmId: _farmId, id: _id, createdAt: _createdAt,
      geometryHash: _hash, geometryVersion: _version,
      isActive: _active, isRevoked: _revoked, deletedAt: _deleted,
      geoJson, ...mutable
    } = body;
    if (
      ["geometryHash", "geometryVersion", "isActive", "isRevoked", "deletedAt"]
        .some((key) => Object.prototype.hasOwnProperty.call(body, key))
    ) {
      return NextResponse.json({ error: "Plot authority fields cannot be edited" }, { status: 403 });
    }
    if (mutable.area !== undefined) {
      const area = Number(mutable.area);
      if (!Number.isFinite(area) || area <= 0) {
        return NextResponse.json({ error: "Invalid plot area" }, { status: 400 });
      }
      mutable.area = area;
    }
    if (geoJson !== undefined) {
      if (!geoJson || typeof geoJson !== "object" || Array.isArray(geoJson)) {
        return NextResponse.json({ error: "Invalid plot geometry" }, { status: 400 });
      }
      try {
        await updatePlotGeometry(currentPlot, session.userId, geoJson);
      } catch (error) {
        console.warn("Plot geometry epoch update rejected:", error);
        return NextResponse.json({ error: "Geometry conflict or unavailable authority" }, { status: 409 });
      }
    }
    const plot = Object.keys(mutable).length
      ? await prisma.plot.update({ where: { id: currentPlot.id }, data: mutable })
      : await prisma.plot.findUniqueOrThrow({ where: { id: currentPlot.id } });
    return NextResponse.json({ success: true, plot });
  } catch (error) {
    console.error("Update plot error:", error);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}
