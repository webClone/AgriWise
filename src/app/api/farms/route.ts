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

function unauthorized() {
  return NextResponse.json({ error: "Authentication required" }, { status: 401 });
}

export async function GET() {
  try {
    const session = await getSession();
    if (!session?.userId) return unauthorized();

    const farms = await prisma.farm.findMany({
      where: { userId: session.userId },
      include: { plots: true },
      orderBy: { createdAt: "desc" },
    });
    return NextResponse.json(farms);
  } catch (error) {
    console.error("Error fetching farms:", error);
    return NextResponse.json({ error: "Error fetching farms" }, { status: 500 });
  }
}

export async function POST(req: Request) {
  try {
    const session = await getSession();
    if (!session?.userId) return unauthorized();

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
    const farm = await prisma.farm.create({
      data: {
        name: name.trim(),
        totalArea: parsedArea,
        wilaya,
        commune: commune || null,
        soilType: soilType || null,
        waterSource: waterSource || null,
        irrigationType: irrigationType || null,
        latitude: wilayaInfo?.lat ?? 28.0339,
        longitude: wilayaInfo?.lng ?? 1.6596,
        userId: session.userId,
      } as any,
    });

    return NextResponse.json(
      { success: true, id: farm.id, farm },
      { status: 201 },
    );
  } catch (error) {
    console.error("Error creating farm:", error);
    return NextResponse.json({ error: "Error creating farm" }, { status: 500 });
  }
}
