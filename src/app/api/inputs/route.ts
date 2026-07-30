import { NextRequest, NextResponse } from "next/server";

import { prisma } from "@/lib/db";
import {
  authenticatedUserId,
  userOwnsCycle,
  userOwnsInput,
} from "@/lib/tenant-authorization";

function unauthorized() {
  return NextResponse.json(
    { success: false, error: "Authentication required" },
    { status: 401 },
  );
}

async function updateCycleTotal(cropCycleId: string) {
  const allInputs = await prisma.inputLog.findMany({
    where: { cropCycleId },
    select: { cost: true },
  });
  await prisma.cropCycle.update({
    where: { id: cropCycleId },
    data: {
      totalCost: allInputs.reduce((sum, input) => sum + (input.cost || 0), 0),
    },
  });
}

export async function GET(request: NextRequest) {
  try {
    const userId = await authenticatedUserId();
    if (!userId) return unauthorized();
    const cropCycleId = request.nextUrl.searchParams.get("cropCycleId");
    if (!cropCycleId) {
      return NextResponse.json(
        { success: false, error: "cropCycleId is required" },
        { status: 400 },
      );
    }
    if (!await userOwnsCycle(userId, cropCycleId)) {
      return NextResponse.json(
        { success: false, error: "Crop cycle not found" },
        { status: 404 },
      );
    }
    const inputs = await prisma.inputLog.findMany({
      where: { cropCycleId },
      orderBy: { appliedAt: "desc" },
    });
    const totals = inputs.reduce((acc, input) => {
      const current = acc[input.type] || { count: 0, totalCost: 0 };
      current.count += 1;
      current.totalCost += input.cost || 0;
      acc[input.type] = current;
      return acc;
    }, {} as Record<string, { count: number; totalCost: number }>);
    return NextResponse.json({ success: true, data: { inputs, totals } });
  } catch (error) {
    console.error("Inputs GET error:", error);
    return NextResponse.json(
      { success: false, error: "Could not load inputs" },
      { status: 500 },
    );
  }
}

export async function POST(request: NextRequest) {
  try {
    const userId = await authenticatedUserId();
    if (!userId) return unauthorized();
    const body = await request.json();
    const {
      cropCycleId,
      type,
      name,
      nameAr,
      brand,
      quantity,
      unit,
      cost,
      appliedAt,
      notes,
    } = body;
    const parsedQuantity = Number(quantity);
    const parsedCost = cost === undefined || cost === null || cost === ""
      ? null
      : Number(cost);
    const applicationDate = appliedAt ? new Date(appliedAt) : new Date();
    if (
      !cropCycleId
      || !type
      || typeof name !== "string"
      || !name.trim()
      || !unit
      || !Number.isFinite(parsedQuantity)
      || parsedQuantity <= 0
      || (parsedCost !== null && !Number.isFinite(parsedCost))
      || Number.isNaN(applicationDate.getTime())
    ) {
      return NextResponse.json(
        { success: false, error: "Invalid input-log fields" },
        { status: 400 },
      );
    }
    if (!await userOwnsCycle(userId, cropCycleId)) {
      return NextResponse.json(
        { success: false, error: "Crop cycle not found" },
        { status: 404 },
      );
    }
    const input = await prisma.inputLog.create({
      data: {
        type,
        name: name.trim(),
        nameAr,
        brand,
        quantity: parsedQuantity,
        unit,
        cost: parsedCost,
        appliedAt: applicationDate,
        notes,
        cropCycleId,
      },
    });
    await updateCycleTotal(cropCycleId);
    return NextResponse.json({ success: true, data: input });
  } catch (error) {
    console.error("Inputs POST error:", error);
    return NextResponse.json(
      { success: false, error: "Could not create input" },
      { status: 500 },
    );
  }
}

export async function DELETE(request: NextRequest) {
  try {
    const userId = await authenticatedUserId();
    if (!userId) return unauthorized();
    const id = request.nextUrl.searchParams.get("id");
    if (!id) {
      return NextResponse.json(
        { success: false, error: "Input ID is required" },
        { status: 400 },
      );
    }
    if (!await userOwnsInput(userId, id)) {
      return NextResponse.json(
        { success: false, error: "Input not found" },
        { status: 404 },
      );
    }
    const input = await prisma.inputLog.delete({ where: { id } });
    await updateCycleTotal(input.cropCycleId);
    return NextResponse.json({ success: true });
  } catch (error) {
    console.error("Inputs DELETE error:", error);
    return NextResponse.json(
      { success: false, error: "Could not delete input" },
      { status: 500 },
    );
  }
}
