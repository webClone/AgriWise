import { NextRequest, NextResponse } from "next/server";
import { authenticateWithCredentials } from "@/lib/auth";
import { createSessionCookie } from "@/lib/session";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { identifier, password } = body;

    if (!identifier || !password) {
      return NextResponse.json(
        { success: false, error: "Identifier (phone or email) and password are required." },
        { status: 400 }
      );
    }

    const user = await authenticateWithCredentials(identifier, password);

    if (!user) {
      return NextResponse.json(
        { success: false, error: "Invalid credentials. Please check your phone/email or password." },
        { status: 401 }
      );
    }

    // Generate signed session cookie
    const sessionCookie = await createSessionCookie({
      id: user.id,
      phone: user.phone,
      role: user.role,
    });

    const response = NextResponse.json({
      success: true,
      message: "Authentication successful",
      user: {
        id: user.id,
        name: user.name,
        phone: user.phone,
        email: user.email,
        role: user.role,
        wilaya: user.wilaya,
        wilayaCode: user.wilayaCode,
      },
    });

    response.cookies.set(
      sessionCookie.name,
      sessionCookie.value,
      sessionCookie.options as any
    );

    return response;
  } catch (error) {
    console.error("Login API error:", error);
    return NextResponse.json(
      { success: false, error: "An unexpected error occurred during authentication." },
      { status: 500 }
    );
  }
}
