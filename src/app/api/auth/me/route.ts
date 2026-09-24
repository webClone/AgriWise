import { NextResponse } from "next/server";
import { getSession } from "@/lib/session";
import { prisma } from "@/lib/db";

export async function GET() {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ authenticated: false, role: null, user: null }, { status: 200 });
  }

  try {
    const user = await prisma.user.findUnique({
      where: { id: session.userId },
      select: {
        id: true,
        name: true,
        nameAr: true,
        phone: true,
        email: true,
        role: true,
        wilaya: true,
        wilayaCode: true,
      },
    });

    if (!user) {
      return NextResponse.json({
        authenticated: true,
        role: session.role,
        user: {
          id: session.userId,
          phone: session.phone,
          role: session.role,
          name: "AgriWise User",
        },
      }, { status: 200 });
    }

    return NextResponse.json({
      authenticated: true,
      role: user.role,
      user,
    }, { status: 200 });
  } catch (error) {
    console.error("Failed to fetch user in /api/auth/me:", error);
    return NextResponse.json({
      authenticated: true,
      role: session.role,
      user: {
        id: session.userId,
        phone: session.phone,
        role: session.role,
      },
    }, { status: 200 });
  }
}
