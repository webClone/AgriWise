// Auth API - OTP Verify
import { NextRequest, NextResponse } from "next/server";
import { verifyOTP, getOrCreateUser } from "@/lib/auth";
import { createSessionCookie } from "@/lib/session";

// Rate limiter: max 5 verify attempts per phone per 15 minutes
const verifyRateMap = new Map<string, { count: number; windowStart: number }>();
const VERIFY_WINDOW_MS = 15 * 60 * 1000; // 15 minutes
const VERIFY_MAX_ATTEMPTS = 5;

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { phone, code, name, wilaya, wilayaCode } = body;

    if (!phone || !code) {
      return NextResponse.json(
        { success: false, error: "Phone number and verification code are required" },
        { status: 400 }
      );
    }

    // Rate limiting check
    const now = Date.now();
    const rateEntry = verifyRateMap.get(phone);
    if (rateEntry) {
      if (now - rateEntry.windowStart < VERIFY_WINDOW_MS) {
        if (rateEntry.count >= VERIFY_MAX_ATTEMPTS) {
          return NextResponse.json(
            { success: false, error: "Too many attempts. Wait 15 minutes." },
            { status: 429 }
          );
        }
        rateEntry.count++;
      } else {
        rateEntry.count = 1;
        rateEntry.windowStart = now;
      }
    } else {
      verifyRateMap.set(phone, { count: 1, windowStart: now });
    }

    const isValid = await verifyOTP(phone, code);

    if (!isValid) {
      return NextResponse.json(
        { success: false, error: "Invalid or expired verification code" },
        { status: 400 }
      );
    }

    // Get or create user
    const user = await getOrCreateUser(phone, { name, wilaya, wilayaCode });

    if (!user) {
      return NextResponse.json(
        { success: false, error: "Failed to create user" },
        { status: 500 }
      );
    }

    // Create signed session cookie
    const sessionCookie = await createSessionCookie({
      id: user.id,
      phone: user.phone,
      role: user.role,
    });

    const response = NextResponse.json({
      success: true,
      message: "Verification successful",
      user: {
        id: user.id,
        phone: user.phone,
        name: user.name,
        role: user.role,
        isVerified: user.isVerified,
      },
      isNewUser: false,
    });

    // Set session cookie on the response
    response.cookies.set(
      sessionCookie.name,
      sessionCookie.value,
      sessionCookie.options as any
    );

    return response;
  } catch (error) {
    console.error("OTP verify error:", error);
    return NextResponse.json(
      { success: false, error: "Something went wrong. Please try again." },
      { status: 500 }
    );
  }
}
