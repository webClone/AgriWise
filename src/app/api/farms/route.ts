
import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { ObjectId } from "bson";
import wilayasData from "@/data/algeria/wilayas.json";

interface RawUser {
  _id: { $oid?: string } | ObjectId;
  name: string;
  phone: string;
}

interface Wilaya {
  code: string;
  nameAr: string;
  nameFr: string;
  nameEn: string;
  lat: number;
  lng: number;
  climate: string;
}

// GET /api/farms
export async function GET() {
  try {
    const farms = await prisma.farm.findMany({
      include: { plots: true },
      orderBy: { createdAt: 'desc' }
    });
    return NextResponse.json(farms);
  } catch (error) {
    console.error("Error fetching farms:", error);
    return NextResponse.json({ error: "Error fetching farms" }, { status: 500 });
  }
}

// POST /api/farms - Create a new farm
export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { name, totalArea, wilaya, commune, soilType, waterSource, irrigationType } = body;

    // Validate required fields
    if (!name || !totalArea || !wilaya) {
      return NextResponse.json(
        { error: "Missing required fields: name, totalArea, wilaya" }, 
        { status: 400 }
      );
    }

    // Look up the wilaya to get coordinates
    const wilayaInfo = (wilayasData.wilayas as Wilaya[]).find(
      w => w.nameAr === wilaya || w.nameFr === wilaya || w.nameEn === wilaya || w.code === wilaya
    );
    
    // Default to center of Algeria if wilaya not found
    const latitude = wilayaInfo?.lat ?? 28.0339;
    const longitude = wilayaInfo?.lng ?? 1.6596;

    const timestamp = Date.now();
    const dateObj = { $date: { $numberLong: String(timestamp) } };

    // Find or create a user using raw MongoDB commands (to avoid transaction issues)
    const existingUsers = await prisma.$runCommandRaw({
      find: "User",
      filter: {},
      limit: 1
    }) as { cursor?: { firstBatch?: RawUser[] } };

    let userId: ObjectId;

    if (!existingUsers.cursor?.firstBatch?.length) {
      // Create a default demo user
      const newUserId = new ObjectId();
      await prisma.$runCommandRaw({
        insert: "User",
        documents: [{
          _id: newUserId,
          phone: "+213555000000",
          name: "مستخدم تجريبي",
          nameAr: "مستخدم تجريبي",
          role: "SMALL_FARMER",
          wilaya: "الجزائر",
          wilayaCode: "16",
          language: "ar",
          isVerified: true,
          isActive: true,
          createdAt: dateObj,
          updatedAt: dateObj,
        }]
      });
      userId = newUserId;
    } else {
      const existingUser = existingUsers.cursor.firstBatch[0];
      // Handle both raw MongoDB format and ObjectId format
      const rawId = existingUser._id as { $oid?: string };
      const userIdStr = rawId.$oid ? rawId.$oid : String(existingUser._id);
      userId = new ObjectId(userIdStr);
    }

    // Create the farm using raw MongoDB insert - now with coordinates!
    const farmId = new ObjectId();
    
    await prisma.$runCommandRaw({
      insert: "Farm",
      documents: [{
        _id: farmId,
        name,
        totalArea: parseFloat(totalArea),
        wilaya,
        commune: commune || null,
        soilType: soilType || null,
        waterSource: waterSource || null,
        irrigationType: irrigationType || null,
        latitude,  // Added from wilaya data
        longitude, // Added from wilaya data
        userId: userId,
        createdAt: dateObj,
        updatedAt: dateObj,
      }]
    });


    return NextResponse.json(
      { 
        success: true, 
        id: farmId.toHexString(),
        message: "تم إنشاء المزرعة بنجاح" 
      }, 
      { status: 201 }
    );
  } catch (error) {
    console.error("Error creating farm:", error);
    return NextResponse.json(
      { error: "Error creating farm", details: String(error) }, 
      { status: 500 }
    );
  }
}
