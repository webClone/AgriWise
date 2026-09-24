// Auth API - OTP Send
import { NextRequest, NextResponse } from "next/server";
import { sendOTP, validatePhoneNumber } from "@/lib/auth";

// Simple in-memory rate limiter: max 3 OTP sends per phone per 5 minutes
const otpRateMap = new Map<string, { count: number; windowStart: number }>();
const RATE_LIMIT_WINDOW_MS = 5 * 60 * 1000; // 5 minutes
const RATE_LIMIT_MAX = 3;

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { phone } = body;

    if (!phone) {
      return NextResponse.json(
        { success: false, error: "Phone number is required" },
        { status: 400 }
      );
    }

    if (!validatePhoneNumber(phone)) {
      return NextResponse.json(
        { success: false, error: "Invalid phone number. Must start with 05, 06, or 07" },
        { status: 400 }
      );
    }

    // Rate limiting check
    const now = Date.now();
    const rateEntry = otpRateMap.get(phone);
    if (rateEntry) {
      if (now - rateEntry.windowStart < RATE_LIMIT_WINDOW_MS) {
        if (rateEntry.count >= RATE_LIMIT_MAX) {
          return NextResponse.json(
            { success: false, error: "Too many attempts. Wait 5 minutes." },
            { status: 429 }
          );
        }
        rateEntry.count++;
      } else {
        // Reset window
        rateEntry.count = 1;
        rateEntry.windowStart = now;
      }
    } else {
      otpRateMap.set(phone, { count: 1, windowStart: now });
    }

    const result = await sendOTP(phone);

    if (!result.success) {
      return NextResponse.json(
        { success: false, error: result.message },
        { status: 500 }
      );
    }

    return NextResponse.json({
      success: true,
      message: result.message,
      ...(result.code ? { code: result.code, devHint: "Dev Mode: Code provided for convenience" } : {}),
    });
  } catch (error) {
    console.error("OTP send error:", error);
    return NextResponse.json(
      { success: false, error: "Something went wrong. Please try again." },
      { status: 500 }
    );
  }
}
