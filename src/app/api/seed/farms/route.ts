import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { SoilType, WaterSource, IrrigationType } from "@prisma/client";
import { ObjectId } from "bson";

// Demo farms for Algeria (created without user relation to avoid transactions)
const demoFarms = [
  {
    name: "مزرعة الواحة",
    wilaya: "بسكرة",
    commune: "طولقة",
    totalArea: 15.5,
    soilType: SoilType.SANDY,
    waterSource: WaterSource.WELL,
    irrigationType: IrrigationType.DRIP,
    latitude: 34.4572,
    longitude: 5.3722,
  },
  {
    name: "مزرعة النخيل",
    wilaya: "الوادي",
    commune: "قمار",
    totalArea: 8.0,
    soilType: SoilType.SANDY,
    waterSource: WaterSource.WELL,
    irrigationType: IrrigationType.FLOOD,
    latitude: 33.5111,
    longitude: 6.8028,
  },
  {
    name: "مزرعة الحبوب",
    wilaya: "سطيف",
    commune: "عين ولمان",
    totalArea: 45.0,
    soilType: SoilType.LOAM,
    waterSource: WaterSource.RAINFED,
    irrigationType: null,
    latitude: 36.0500,
    longitude: 5.2833,
  },
  {
    name: "مزرعة الزيتون",
    wilaya: "تيزي وزو",
    commune: "ذراع الميزان",
    totalArea: 12.0,
    soilType: SoilType.CLAY,
    waterSource: WaterSource.RIVER,
    irrigationType: IrrigationType.DRIP,
    latitude: 36.6667,
    longitude: 3.8333,
  },
  {
    name: "مزرعة الخضروات",
    wilaya: "البليدة",
    commune: "بوفاريك",
    totalArea: 3.5,
    soilType: SoilType.LOAM,
    waterSource: WaterSource.DAM,
    irrigationType: IrrigationType.SPRINKLER,
    latitude: 36.5667,
    longitude: 2.9167,
  },
];

export async function POST() {
  try {
    // We need to use raw MongoDB operations entirely to avoid Prisma's transaction requirements
    // and also avoid Prisma's DateTime conversion issues when reading back raw-inserted data
    
    // Check for existing user using a raw find command
    const existingUsers = await prisma.$runCommandRaw({
      find: "User",
      filter: {},
      limit: 1
    }) as { cursor?: { firstBatch?: { _id?: { $oid?: string } }[] } };
    
    let userIdStr: string;
    
    // Create date in MongoDB canonical extended JSON v2 format
    // Using $date with $numberLong for proper BSON Date type
    const timestamp = Date.now();
    const dateObj = { $date: { $numberLong: String(timestamp) } };
    
    if (existingUsers.cursor?.firstBatch?.length === 0 || !existingUsers.cursor?.firstBatch?.[0]) {
      // Create a new demo user using raw insert
      const newUserId = new ObjectId();
      
      await prisma.$runCommandRaw({
        insert: "User",
        documents: [{
          _id: newUserId,
          phone: "+213555000000",
          name: "Demo User",
          nameAr: "مستخدم تجريبي",
          email: "demo@agriwise.dz",
          role: "SMALL_FARMER",
          wilaya: "الجزائر",
          wilayaCode: "16",
          commune: "باب الوادي",
          language: "ar",
          isVerified: true,
          isActive: true,
          createdAt: dateObj,
          updatedAt: dateObj,
        }]
      });
      
      userIdStr = newUserId.toHexString();
      console.log("✅ Created demo user via raw insert:", userIdStr);
    } else {
      // Use existing user's ID
      const existingUser = existingUsers.cursor.firstBatch[0];
      userIdStr = existingUser._id?.$oid || String(existingUser._id);
      console.log("✅ Using existing user:", userIdStr);
    }

    // Create demo farms using raw insertOne (no transactions)
    const createdFarms = [];
    for (const farmData of demoFarms) {
      const farmId = new ObjectId();
      const farmTimestamp = Date.now();
      const farmDateObj = { $date: { $numberLong: String(farmTimestamp) } };
      
      await prisma.$runCommandRaw({
        insert: "Farm",
        documents: [{
          _id: farmId,
          ...farmData,
          userId: new ObjectId(userIdStr),
          createdAt: farmDateObj,
          updatedAt: farmDateObj,
        }]
      });
      
      createdFarms.push({ id: farmId.toHexString(), name: farmData.name });
    }

    return NextResponse.json({
      success: true,
      message: `تم إنشاء ${createdFarms.length} مزارع تجريبية`,
      farms: createdFarms
    });

  } catch (error) {
    console.error("Error seeding demo farms:", error);
    return NextResponse.json(
      { success: false, error: String(error) },
      { status: 500 }
    );
  }
}

export async function DELETE() {
  try {
    // Delete all farms and users using raw MongoDB (bypasses Prisma issues)
    await prisma.$runCommandRaw({
      delete: "Farm",
      deletes: [{ q: {}, limit: 0 }]
    });
    
    await prisma.$runCommandRaw({
      delete: "User",
      deletes: [{ q: {}, limit: 0 }]
    });

    return NextResponse.json({
      success: true,
      message: "تم حذف جميع المزارع والمستخدمين"
    });

  } catch (error) {
    console.error("Error clearing data:", error);
    return NextResponse.json(
      { success: false, error: String(error) },
      { status: 500 }
    );
  }
}

export async function GET() {
  return NextResponse.json({
    info: "Demo Farm Seeder API",
    note: "Requires an existing user in database (MongoDB replica set limitation)",
    endpoints: {
      "POST /api/seed/farms": "إنشاء مزارع تجريبية",
      "DELETE /api/seed/farms": "حذف جميع المزارع"
    }
  });
}
