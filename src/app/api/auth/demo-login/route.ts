import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { createSessionCookie } from "@/lib/session";
import { UserRole } from "@prisma/client";

interface DemoPersona {
  phone: string;
  name: string;
  nameAr: string;
  role: UserRole;
  wilaya: string;
  wilayaCode: string;
  farmName: string;
  farmArea: number;
}

const DEMO_PERSONAS: Record<string, DemoPersona> = {
  farmer: {
    phone: "+213555010101",
    name: "Youcef Amrani",
    nameAr: "يوسف عمراني",
    role: UserRole.SMALL_FARMER,
    wilaya: "Blida",
    wilayaCode: "09",
    farmName: "Domaine Amrani (Mitidja Citrus & Olive)",
    farmArea: 14.5,
  },
  agronomist: {
    phone: "+213555020202",
    name: "Dr. Amel Benali",
    nameAr: "د. آمال بن علي",
    role: UserRole.AGRONOMIST,
    wilaya: "Algiers",
    wilayaCode: "16",
    farmName: "Station Pilote Agronomique INRAA",
    farmArea: 45.0,
  },
  sovereign: {
    phone: "+213555030303",
    name: "Sovereign Food Security Agency",
    nameAr: "الديوان الوطني للأمن الغذائي",
    role: UserRole.NATIONAL_GOV,
    wilaya: "Algiers",
    wilayaCode: "16",
    farmName: "Bassin Hydro-Agricole Cheliff Ouest",
    farmArea: 2500.0,
  },
};

export async function POST(request: NextRequest) {
  try {
    const body = await request.json().catch(() => ({}));
    const personaKey = (body.persona || "farmer").toLowerCase();
    const config = DEMO_PERSONAS[personaKey] || DEMO_PERSONAS.farmer;

    // Find or create persona user
    let user = await prisma.user.findFirst({
      where: { phone: config.phone },
    });

    if (!user) {
      user = await prisma.user.create({
        data: {
          phone: config.phone,
          name: config.name,
          nameAr: config.nameAr,
          role: config.role,
          wilaya: config.wilaya,
          wilayaCode: config.wilayaCode,
          isVerified: true,
          isActive: true,
        },
      });

      // Create primary demonstration farm
      try {
        await prisma.farm.create({
          data: {
            name: config.farmName,
            userId: user.id,
            wilaya: config.wilaya,
            totalArea: config.farmArea,
            latitude: 36.47,
            longitude: 2.83,
          },
        });
      } catch (fErr) {
        console.warn("Demo farm creation note:", fErr);
      }
    }

    // Generate signed session cookie
    const sessionCookie = await createSessionCookie({
      id: user.id,
      phone: user.phone,
      role: user.role,
    });

    const response = NextResponse.json({
      success: true,
      message: `Signed in as ${user.name}`,
      user: {
        id: user.id,
        name: user.name,
        nameAr: user.nameAr,
        phone: user.phone,
        role: user.role,
        wilaya: user.wilaya,
      },
      redirect: "/farm",
    });

    response.cookies.set(
      sessionCookie.name,
      sessionCookie.value,
      sessionCookie.options as any
    );

    return response;
  } catch (error) {
    console.error("Demo login error:", error);
    return NextResponse.json(
      { success: false, error: "Failed to initialize demo session." },
      { status: 500 }
    );
  }
}
