// Weather API - Get current weather and forecast
import { NextRequest, NextResponse } from "next/server";
import { fetchWeather, wilayaCoordinates } from "@/lib/weather";

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const wilayaCode = searchParams.get("wilaya") || "17"; // Default to Djelfa

    // Validate wilaya code
    if (!wilayaCoordinates[wilayaCode]) {
      return NextResponse.json(
        { success: false, error: "رمز الولاية غير صالح" },
        { status: 400 }
      );
    }

    const weather = await fetchWeather(wilayaCode);

    if (!weather) {
      return NextResponse.json(
        { success: false, error: "فشل الحصول على بيانات الطقس" },
        { status: 500 }
      );
    }

    return NextResponse.json({
      success: true,
      data: weather,
    });
  } catch (error) {
    console.error("Weather API error:", error);
    return NextResponse.json(
      { success: false, error: "حدث خطأ. حاول مرة أخرى." },
      { status: 500 }
    );
  }
}
