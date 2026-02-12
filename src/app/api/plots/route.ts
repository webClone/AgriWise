// Plots API - CRUD operations
import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { ObjectId } from "bson";

// GET - List plots for a farm
export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const farmId = searchParams.get("farmId");

    if (!farmId) {
      return NextResponse.json(
        { success: false, error: "معرف المزرعة مطلوب" },
        { status: 400 }
      );
    }

    if (!ObjectId.isValid(farmId)) {
      return NextResponse.json(
        { success: false, error: "معرف المزرعة غير صالح" },
        { status: 400 }
      );
    }

    const result = await prisma.$runCommandRaw({
      find: "Plot",
      filter: { farmId: new ObjectId(farmId) }
    }) as { cursor?: { firstBatch?: Array<{
      _id: { $oid?: string };
      name: string;
      nameAr?: string;
      area: number;
      soilType?: string;
      irrigation?: string;
    }> } };

    const plots = (result.cursor?.firstBatch || []).map(p => ({
      id: p._id.$oid || String(p._id),
      name: p.name,
      nameAr: p.nameAr,
      area: p.area,
      soilType: p.soilType,
      irrigation: p.irrigation,
    }));

    return NextResponse.json({
      success: true,
      data: plots,
    });
  } catch (error) {
    console.error("Plots GET error:", error);
    return NextResponse.json(
      { success: false, error: "حدث خطأ. حاول مرة أخرى." },
      { status: 500 }
    );
  }
}

// POST - Create a new plot
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { farmId, name, nameAr, area, soilType, irrigation, geoJson } = body;

    if (!farmId || !name || !area) {
      return NextResponse.json(
        { success: false, error: "معرف المزرعة واسم القطعة والمساحة مطلوبان" },
        { status: 400 }
      );
    }

    if (!ObjectId.isValid(farmId)) {
      return NextResponse.json(
        { success: false, error: "معرف المزرعة غير صالح" },
        { status: 400 }
      );
    }

    const timestamp = Date.now();
    const dateObj = { $date: { $numberLong: String(timestamp) } };

    // Create the plot using raw MongoDB insert
    const plotId = new ObjectId();
    
    await prisma.$runCommandRaw({
      insert: "Plot",
      documents: [{
        _id: plotId,
        name,
        nameAr: nameAr || name,
        area: parseFloat(area),
        soilType: soilType || null,
        irrigation: irrigation || null,
        geoJson: geoJson || null,
        farmId: new ObjectId(farmId),
        createdAt: dateObj,
        updatedAt: dateObj,
      }]
    });

    // Register plot with AI data collector for automatic data collection
    // This enables weather/satellite data logging for ML training
    const PYTHON_API_URL = process.env.PYTHON_API_URL || "http://127.0.0.1:8000";
    try {
      // Extract coordinates from geoJson if available
      let coordinates = { lat: 0, lng: 0 };
      if (geoJson?.geometry?.coordinates) {
        const coords = geoJson.geometry.coordinates;
        if (Array.isArray(coords[0])) {
          // Polygon - use centroid approximation
          const flat = coords[0];
          const lngs = flat.map((c: number[]) => c[0]);
          const lats = flat.map((c: number[]) => c[1]);
          coordinates = {
            lat: lats.reduce((a: number, b: number) => a + b, 0) / lats.length,
            lng: lngs.reduce((a: number, b: number) => a + b, 0) / lngs.length
          };
        } else {
          coordinates = { lat: coords[1], lng: coords[0] };
        }
      }

      await fetch(`${PYTHON_API_URL}/collector/register-plot`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          farm_id: farmId,
          plot_id: plotId.toHexString(),
          coordinates,
          crop: soilType || "unknown", // Use crop from plot data if available
          area: parseFloat(area)
        })
      });
      console.log(`📊 Plot ${plotId.toHexString()} registered for data collection`);
    } catch (collectorError) {
      // Don't fail plot creation if collector registration fails
      console.warn(`⚠️ Could not register plot for data collection:`, collectorError);
    }

    return NextResponse.json({
      success: true,
      data: {
        id: plotId.toHexString(),
        name,
        area: parseFloat(area),
      },
      message: "تم إنشاء القطعة بنجاح"
    }, { status: 201 });
  } catch (error) {
    console.error("Plots POST error:", error);
    return NextResponse.json(
      { success: false, error: "حدث خطأ. حاول مرة أخرى." },
      { status: 500 }
    );
  }
}

// PUT - Update a plot
export async function PUT(request: NextRequest) {
  try {
    const body = await request.json();
    const { id, name, nameAr, area, soilType, irrigation, geoJson } = body;

    if (!id) {
      return NextResponse.json(
        { success: false, error: "معرف القطعة مطلوب" },
        { status: 400 }
      );
    }

    const plot = await prisma.plot.update({
      where: { id },
      data: {
        ...(name && { name }),
        ...(nameAr && { nameAr }),
        ...(area && { area: parseFloat(area) }),
        ...(soilType && { soilType }),
        ...(irrigation && { irrigation }),
        ...(geoJson && { geoJson }),
      },
    });

    return NextResponse.json({
      success: true,
      data: plot,
    });
  } catch (error) {
    console.error("Plots PUT error:", error);
    return NextResponse.json(
      { success: false, error: "حدث خطأ. حاول مرة أخرى." },
      { status: 500 }
    );
  }
}

// DELETE - Delete a plot
export async function DELETE(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const id = searchParams.get("id");

    if (!id) {
      return NextResponse.json(
        { success: false, error: "معرف القطعة مطلوب" },
        { status: 400 }
      );
    }

    await prisma.plot.delete({
      where: { id },
    });

    return NextResponse.json({
      success: true,
      message: "تم حذف القطعة بنجاح",
    });
  } catch (error) {
    console.error("Plots DELETE error:", error);
    return NextResponse.json(
      { success: false, error: "حدث خطأ. حاول مرة أخرى." },
      { status: 500 }
    );
  }
}
