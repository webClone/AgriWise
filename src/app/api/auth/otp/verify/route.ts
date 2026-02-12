// Auth API - OTP Verify
import { NextRequest, NextResponse } from "next/server";
import { verifyOTP, getOrCreateUser } from "@/lib/auth";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { phone, code, name, wilaya, wilayaCode } = body;

    if (!phone || !code) {
      return NextResponse.json(
        { success: false, error: "رقم الهاتف ورمز التحقق مطلوبان" },
        { status: 400 }
      );
    }

    const isValid = await verifyOTP(phone, code);

    if (!isValid) {
      return NextResponse.json(
        { success: false, error: "رمز التحقق غير صحيح أو منتهي الصلاحية" },
        { status: 400 }
      );
    }

    // Get or create user
    const user = await getOrCreateUser(phone, { name, wilaya, wilayaCode });

    return NextResponse.json({
      success: true,
      message: "تم التحقق بنجاح",
      user: user ? {
        id: user.id,
        phone: user.phone,
        name: user.name,
        wilaya: user.wilaya,
        wilayaCode: user.wilayaCode,
        role: user.role,
        isVerified: user.isVerified,
      } : null,
      isNewUser: !user,
    });
  } catch (error) {
    console.error("OTP verify error:", error);
    return NextResponse.json(
      { success: false, error: "حدث خطأ. حاول مرة أخرى." },
      { status: 500 }
    );
  }
}
