import { ObjectId } from "bson";
import { NextResponse } from "next/server";

import wilayasData from "@/data/algeria/wilayas.json";
import { prisma } from "@/lib/prisma";
import { getSession } from "@/lib/session";

interface Wilaya {
  code: string;
  nameAr: string;
  nameFr: string;
  nameEn: string;
  lat: number;
  lng: number;
}

export async function PUT(
  req: Request,
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
      return NextResponse.json({ error: "Invalid ID format" }, { status: 400 });
    }
    const ownedFarm = await prisma.farm.findFirst({
      where: { id, userId: session.userId },
      select: { id: true },
    });
    if (!ownedFarm) {
      return NextResponse.json({ error: "Farm not found" }, { status: 404 });
    }

    const body = await req.json();
    const {
      name,
      totalArea,
      wilaya,
      commune,
      soilType,
      waterSource,
      irrigationType,
    } = body;
    const parsedArea = Number(totalArea);
    if (
      typeof name !== "string"
      || !name.trim()
      || typeof wilaya !== "string"
      || !wilaya.trim()
      || !Number.isFinite(parsedArea)
      || parsedArea <= 0
    ) {
      return NextResponse.json(
        { error: "Valid name, totalArea, and wilaya are required" },
        { status: 400 },
      );
    }
    const wilayaInfo = (wilayasData.wilayas as Wilaya[]).find(
      (candidate) => (
        candidate.nameAr === wilaya
        || candidate.nameFr === wilaya
        || candidate.nameEn === wilaya
        || candidate.code === wilaya
      ),
    );
    const farm = await prisma.farm.update({
      where: { id: ownedFarm.id },
      data: {
        name: name.trim(),
        totalArea: parsedArea,
        wilaya,
        commune: commune || null,
        soilType: soilType || null,
        waterSource: waterSource || null,
        irrigationType: irrigationType || null,
        ...(wilayaInfo
          ? { latitude: wilayaInfo.lat, longitude: wilayaInfo.lng }
          : {}),
      } as any,
    });
    return NextResponse.json({ success: true, farm });
  } catch (error) {
    console.error("Error updating farm:", error);
    return NextResponse.json({ error: "Error updating farm" }, { status: 500 });
  }
}
