// Auth API - OTP Send
import { NextRequest, NextResponse } from "next/server";
import { sendOTP, validatePhoneNumber } from "@/lib/auth";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { phone } = body;

    if (!phone) {
      return NextResponse.json(
        { success: false, error: "رقم الهاتف مطلوب" },
        { status: 400 }
      );
    }

    if (!validatePhoneNumber(phone)) {
      return NextResponse.json(
        { success: false, error: "رقم الهاتف غير صالح. يجب أن يبدأ بـ 05 أو 06 أو 07" },
        { status: 400 }
      );
    }

    const result = await sendOTP(phone);

    if (!result.success) {
      return NextResponse.json(
        { success: false, error: result.message },
        { status: 500 }
      );
    }

    // In development, include the OTP for testing
    const response: { success: boolean; message: string; code?: string } = {
      success: true,
      message: result.message,
    };

    if (process.env.NODE_ENV === "development" && result.code) {
      response.code = result.code;
    }

    return NextResponse.json(response);
  } catch (error) {
    console.error("OTP send error:", error);
    return NextResponse.json(
      { success: false, error: "حدث خطأ. حاول مرة أخرى." },
      { status: 500 }
    );
  }
}
