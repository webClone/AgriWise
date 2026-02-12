
import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { ObjectId } from "bson";
import wilayasData from "@/data/algeria/wilayas.json";

interface Wilaya {
  code: string;
  nameAr: string;
  nameFr: string;
  nameEn: string;
  lat: number;
  lng: number;
  climate: string;
}

// PUT /api/farms/[id] - Update farm details
export async function PUT(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    
    if (!ObjectId.isValid(id)) {
        return NextResponse.json({ error: "Invalid ID format" }, { status: 400 });
    }

    const body = await req.json();
    const { 
        name, 
        totalArea, 
        wilaya, 
        commune, 
        soilType, 
        waterSource, 
        irrigationType 
    } = body;

    // Validate required fields
    if (!name || !totalArea || !wilaya) {
      return NextResponse.json(
        { error: "Missing required fields: name, totalArea, wilaya" }, 
        { status: 400 }
      );
    }

    // Look up the wilaya to get coordinates if wilaya changed or needed
    const wilayaInfo = (wilayasData.wilayas as Wilaya[]).find(
      w => w.nameAr === wilaya || w.nameFr === wilaya || w.nameEn === wilaya || w.code === wilaya
    );
    
    const updateData: any = {
        name,
        totalArea: parseFloat(totalArea),
        wilaya,
        commune: commune || null,
        soilType: soilType || null,
        waterSource: waterSource || null,
        irrigationType: irrigationType || null,
        updatedAt: { $date: { $numberLong: String(Date.now()) } }
    };

    // Update coordinates if wilaya info is found
    if (wilayaInfo) {
        updateData.latitude = wilayaInfo.lat;
        updateData.longitude = wilayaInfo.lng;
    }

    // Use raw command to update
    const result = await prisma.$runCommandRaw({
        update: "Farm",
        updates: [{
            q: { _id: new ObjectId(id) },
            u: { $set: updateData }
        }]
    }) as { n: number, nModified: number };

    if (result.nModified === 0 && result.n === 0) {
        return NextResponse.json({ error: "Farm not found" }, { status: 404 });
    }

    return NextResponse.json({ success: true, message: "تم تحديث المزرعة بنجاح" });

  } catch (error) {
    console.error("Error updating farm:", error);
    return NextResponse.json(
      { error: "Error updating farm", details: String(error) }, 
      { status: 500 }
    );
  }
}
