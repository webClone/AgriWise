// Input logging API - Track seeds, fertilizers, pesticides, etc.
import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db";

// GET - List inputs for a crop cycle
export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const cropCycleId = searchParams.get("cropCycleId");

    if (!cropCycleId) {
      return NextResponse.json(
        { success: false, error: "معرف دورة المحصول مطلوب" },
        { status: 400 }
      );
    }

    const inputs = await prisma.inputLog.findMany({
      where: { cropCycleId },
      orderBy: { appliedAt: "desc" },
    });

    // Calculate totals by type
    const totals = inputs.reduce((acc, input) => {
      if (!acc[input.type]) {
        acc[input.type] = { count: 0, totalCost: 0 };
      }
      acc[input.type].count++;
      acc[input.type].totalCost += input.cost || 0;
      return acc;
    }, {} as Record<string, { count: number; totalCost: number }>);

    return NextResponse.json({
      success: true,
      data: { inputs, totals },
    });
  } catch (error) {
    console.error("Inputs GET error:", error);
    return NextResponse.json(
      { success: false, error: "حدث خطأ. حاول مرة أخرى." },
      { status: 500 }
    );
  }
}

// POST - Log a new input
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { cropCycleId, type, name, nameAr, brand, quantity, unit, cost, appliedAt, notes } = body;

    if (!cropCycleId || !type || !name || !quantity || !unit) {
      return NextResponse.json(
        { success: false, error: "جميع الحقول المطلوبة يجب ملؤها" },
        { status: 400 }
      );
    }

    const input = await prisma.inputLog.create({
      data: {
        type,
        name,
        nameAr,
        brand,
        quantity: parseFloat(quantity),
        unit,
        cost: cost ? parseFloat(cost) : null,
        appliedAt: appliedAt ? new Date(appliedAt) : new Date(),
        notes,
        cropCycleId,
      },
    });

    // Update crop cycle total cost
    const allInputs = await prisma.inputLog.findMany({
      where: { cropCycleId },
    });
    const totalCost = allInputs.reduce((sum, i) => sum + (i.cost || 0), 0);
    
    await prisma.cropCycle.update({
      where: { id: cropCycleId },
      data: { totalCost },
    });

    return NextResponse.json({
      success: true,
      data: input,
    });
  } catch (error) {
    console.error("Inputs POST error:", error);
    return NextResponse.json(
      { success: false, error: "حدث خطأ. حاول مرة أخرى." },
      { status: 500 }
    );
  }
}

// DELETE - Remove an input
export async function DELETE(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const id = searchParams.get("id");

    if (!id) {
      return NextResponse.json(
        { success: false, error: "معرف المدخل مطلوب" },
        { status: 400 }
      );
    }

    const input = await prisma.inputLog.delete({
      where: { id },
    });

    // Recalculate crop cycle total cost
    const allInputs = await prisma.inputLog.findMany({
      where: { cropCycleId: input.cropCycleId },
    });
    const totalCost = allInputs.reduce((sum, i) => sum + (i.cost || 0), 0);
    
    await prisma.cropCycle.update({
      where: { id: input.cropCycleId },
      data: { totalCost },
    });

    return NextResponse.json({
      success: true,
      message: "تم حذف المدخل بنجاح",
    });
  } catch (error) {
    console.error("Inputs DELETE error:", error);
    return NextResponse.json(
      { success: false, error: "حدث خطأ. حاول مرة أخرى." },
      { status: 500 }
    );
  }
}
