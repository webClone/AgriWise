import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { validatePhoneNumber, hashPassword } from "@/lib/auth";
import { createSessionCookie } from "@/lib/session";
import { UserRole } from "@prisma/client";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const {
      name,
      phone,
      wilaya,
      wilayaCode,
      commune,
      email,
      password,
      role = "SMALL_FARMER",
      farmName,
      farmArea,
    } = body;

    // Validation
    if (!name || !name.trim()) {
      return NextResponse.json(
        { success: false, error: "Full name is required." },
        { status: 400 }
      );
    }

    if (!phone || !validatePhoneNumber(phone)) {
      return NextResponse.json(
        { success: false, error: "A valid Algerian phone number is required (05, 06, 07)." },
        { status: 400 }
      );
    }

    if (!wilaya || !wilayaCode) {
      return NextResponse.json(
        { success: false, error: "Wilaya selection is required." },
        { status: 400 }
      );
    }

    const cleanedPhone = phone.replace(/[\s-]/g, "");

    // Check if phone already registered
    const existingUser = await prisma.user.findFirst({
      where: {
        OR: [
          { phone: cleanedPhone },
          ...(email ? [{ email: email.toLowerCase().trim() }] : []),
        ],
      },
    });

    if (existingUser) {
      return NextResponse.json(
        { success: false, error: "An account with this phone number or email already exists. Please log in." },
        { status: 409 }
      );
    }

    // Hash password if provided
    const hashedPassword = password && password.length >= 6 ? hashPassword(password) : null;

    // Whitelist roles eligible for public self-registration.
    // Privileged administrative and governmental roles (ADMIN, NATIONAL_GOV, LOCAL_GOV)
    // require controlled internal provisioning and cannot be self-assigned.
    const PUBLIC_REGISTRATION_ROLES: UserRole[] = [
      UserRole.SMALL_FARMER,
      UserRole.MEDIUM_FARMER,
      UserRole.LARGE_FARMER,
      UserRole.COOPERATIVE_MANAGER,
      UserRole.AGRONOMIST,
      UserRole.INPUT_SUPPLIER,
      UserRole.TRANSPORTER,
      UserRole.STORAGE_OPERATOR,
      UserRole.RESEARCHER,
    ];

    const assignedRole = PUBLIC_REGISTRATION_ROLES.includes(role as UserRole)
      ? (role as UserRole)
      : UserRole.SMALL_FARMER;

    // Create user
    const newUser = await prisma.user.create({
      data: {
        name: name.trim(),
        phone: cleanedPhone,
        email: email ? email.toLowerCase().trim() : null,
        password: hashedPassword,
        wilaya: wilaya.trim(),
        wilayaCode: String(wilayaCode).padStart(2, "0"),
        commune: commune ? commune.trim() : null,
        role: assignedRole,
        isVerified: true,
        isActive: true,
      },
    });

    // Optionally create an initial farm if farmName is provided
    if (farmName && farmName.trim()) {
      try {
        await prisma.farm.create({
          data: {
            name: farmName.trim(),
            userId: newUser.id,
            wilaya: newUser.wilaya,
            commune: newUser.commune,
            totalArea: Number(farmArea) > 0 ? Number(farmArea) : 10.0,
          },
        });
      } catch (farmError) {
        console.warn("Initial farm creation note:", farmError);
      }
    }

    // Create signed session cookie
    const sessionCookie = await createSessionCookie({
      id: newUser.id,
      phone: newUser.phone,
      role: newUser.role,
    });

    const response = NextResponse.json({
      success: true,
      message: "Registration completed successfully",
      user: {
        id: newUser.id,
        name: newUser.name,
        phone: newUser.phone,
        email: newUser.email,
        role: newUser.role,
        wilaya: newUser.wilaya,
        wilayaCode: newUser.wilayaCode,
      },
    });

    response.cookies.set(
      sessionCookie.name,
      sessionCookie.value,
      sessionCookie.options as any
    );

    return response;
  } catch (error) {
    console.error("Registration API error:", error);
    return NextResponse.json(
      { success: false, error: "Registration failed. Please try again." },
      { status: 500 }
    );
  }
}
