import { ObjectId } from "bson";
import { NextRequest, NextResponse } from "next/server";

import { prisma } from "@/lib/prisma";
import { getSession } from "@/lib/session";

function unauthorized() {
  return NextResponse.json(
    { success: false, error: "Authentication required" },
    { status: 401 },
  );
}

async function findOwnedFarm(farmId: string, userId: string) {
  return prisma.farm.findFirst({
    where: { id: farmId, userId },
    select: { id: true },
  });
}

async function findOwnedPlot(plotId: string, userId: string) {
  return prisma.plot.findFirst({
    where: { id: plotId, farm: { userId } },
    select: { id: true },
  });
}

export async function GET(request: NextRequest) {
  try {
    const session = await getSession();
    if (!session?.userId) return unauthorized();
    const farmId = request.nextUrl.searchParams.get("farmId");
    if (!farmId || !ObjectId.isValid(farmId)) {
      return NextResponse.json(
        { success: false, error: "A valid farmId is required" },
        { status: 400 },
      );
    }
    if (!await findOwnedFarm(farmId, session.userId)) {
      return NextResponse.json(
        { success: false, error: "Farm not found" },
        { status: 404 },
      );
    }
    const plots = await prisma.plot.findMany({
      where: { farmId },
      orderBy: { createdAt: "desc" },
    });
    return NextResponse.json({ success: true, data: plots });
  } catch (error) {
    console.error("Plots GET error:", error);
    return NextResponse.json(
      { success: false, error: "Could not load plots" },
      { status: 500 },
    );
  }
}

export async function POST(request: NextRequest) {
  try {
    const session = await getSession();
    if (!session?.userId) return unauthorized();
    const body = await request.json();
    const { farmId, name, nameAr, area, soilType, irrigation, geoJson } = body;
    const parsedArea = Number(area);
    if (
      typeof farmId !== "string"
      || !ObjectId.isValid(farmId)
      || typeof name !== "string"
      || !name.trim()
      || !Number.isFinite(parsedArea)
      || parsedArea <= 0
    ) {
      return NextResponse.json(
        { success: false, error: "Valid farmId, name, and area are required" },
        { status: 400 },
      );
    }
    if (!await findOwnedFarm(farmId, session.userId)) {
      return NextResponse.json(
        { success: false, error: "Farm not found" },
        { status: 404 },
      );
    }
    const plot = await prisma.plot.create({
      data: {
        farmId,
        name: name.trim(),
        nameAr: nameAr || name.trim(),
        area: parsedArea,
        soilType: soilType || null,
        irrigation: irrigation || null,
        geoJson: geoJson || null,
        physicalConstraints: [],
      } as any,
    });

    const pythonApiUrl = (
      process.env.PYTHON_API_URL || "http://127.0.0.1:8000"
    ).replace(/\/$/, "");
    try {
      let coordinates = { lat: 0, lng: 0 };
      const rawCoordinates = geoJson?.geometry?.coordinates;
      if (Array.isArray(rawCoordinates)) {
        const ring = Array.isArray(rawCoordinates[0]?.[0])
          ? rawCoordinates[0]
          : null;
        if (ring?.length) {
          const valid = ring.filter(
            (point: unknown) => (
              Array.isArray(point)
              && point.length >= 2
              && Number.isFinite(Number(point[0]))
              && Number.isFinite(Number(point[1]))
            ),
          );
          if (valid.length) {
            coordinates = {
              lng: valid.reduce(
                (sum: number, point: number[]) => sum + Number(point[0]), 0,
              ) / valid.length,
              lat: valid.reduce(
                (sum: number, point: number[]) => sum + Number(point[1]), 0,
              ) / valid.length,
            };
          }
        }
      }
      await fetch(`${pythonApiUrl}/collector/register-plot`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          farm_id: farmId,
          plot_id: plot.id,
          coordinates,
          crop: "unknown",
          area: parsedArea,
        }),
      });
    } catch (collectorError) {
      console.warn("Could not register plot for data collection:", collectorError);
    }
    return NextResponse.json(
      { success: true, data: plot },
      { status: 201 },
    );
  } catch (error) {
    console.error("Plots POST error:", error);
    return NextResponse.json(
      { success: false, error: "Could not create plot" },
      { status: 500 },
    );
  }
}

export async function PUT(request: NextRequest) {
  try {
    const session = await getSession();
    if (!session?.userId) return unauthorized();
    const body = await request.json();
    const { id, farmId: _farmId, createdAt: _createdAt, ...mutable } = body;
    if (typeof id !== "string" || !ObjectId.isValid(id)) {
      return NextResponse.json(
        { success: false, error: "A valid plot ID is required" },
        { status: 400 },
      );
    }
    const owned = await findOwnedPlot(id, session.userId);
    if (!owned) {
      return NextResponse.json(
        { success: false, error: "Plot not found" },
        { status: 404 },
      );
    }
    if (mutable.area !== undefined) {
      const parsedArea = Number(mutable.area);
      if (!Number.isFinite(parsedArea) || parsedArea <= 0) {
        return NextResponse.json(
          { success: false, error: "Invalid plot area" },
          { status: 400 },
        );
      }
      mutable.area = parsedArea;
    }
    const plot = await prisma.plot.update({
      where: { id: owned.id },
      data: mutable,
    });
    return NextResponse.json({ success: true, data: plot });
  } catch (error) {
    console.error("Plots PUT error:", error);
    return NextResponse.json(
      { success: false, error: "Could not update plot" },
      { status: 500 },
    );
  }
}

export async function DELETE(request: NextRequest) {
  try {
    const session = await getSession();
    if (!session?.userId) return unauthorized();
    const id = request.nextUrl.searchParams.get("id");
    if (!id || !ObjectId.isValid(id)) {
      return NextResponse.json(
        { success: false, error: "A valid plot ID is required" },
        { status: 400 },
      );
    }
    const owned = await findOwnedPlot(id, session.userId);
    if (!owned) {
      return NextResponse.json(
        { success: false, error: "Plot not found" },
        { status: 404 },
      );
    }
    await prisma.plot.delete({ where: { id: owned.id } });
    return NextResponse.json({ success: true });
  } catch (error) {
    console.error("Plots DELETE error:", error);
    return NextResponse.json(
      { success: false, error: "Could not delete plot" },
      { status: 500 },
    );
  }
}
