// AI Chat API - Gemini-powered agricultural advisor
import { NextRequest, NextResponse } from "next/server";
import { getAIAdvice, getQuickAdvice } from "@/lib/agribrain/gemini-advisor";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { message, chatHistory, farmContext, quickTopic, cropCode } = body;

    // Quick advice mode
    if (quickTopic && cropCode) {
      const advice = await getQuickAdvice(quickTopic, cropCode, farmContext);
      return NextResponse.json({
        success: true,
        response: advice,
        isQuickAdvice: true,
      });
    }

    // Chat mode
    if (!message) {
      return NextResponse.json(
        { success: false, error: "الرسالة مطلوبة" },
        { status: 400 }
      );
    }

    const result = await getAIAdvice(message, chatHistory || [], farmContext);

    if (!result.success) {
      return NextResponse.json(
        { success: false, error: result.error },
        { status: 500 }
      );
    }

    return NextResponse.json({
      success: true,
      response: result.response,
    });
  } catch (error) {
    console.error("AI Chat API error:", error);
    return NextResponse.json(
      { success: false, error: "حدث خطأ في معالجة الطلب" },
      { status: 500 }
    );
  }
}

// GET - Check if AI is available
export async function GET() {
  const hasApiKey = !!process.env.GEMINI_API_KEY;
  
  return NextResponse.json({
    success: true,
    available: hasApiKey,
    model: "gemini-1.5-flash",
    features: [
      { code: "chat", nameAr: "محادثة مع المستشار", available: hasApiKey },
      { code: "quick", nameAr: "نصائح سريعة", available: hasApiKey },
      { code: "analysis", nameAr: "تحليل ذكي", available: true }, // Rule-based always available
    ],
    quickTopics: [
      { code: "irrigation", nameAr: "الري", icon: "💧" },
      { code: "fertilizer", nameAr: "التسميد", icon: "🌱" },
      { code: "pests", nameAr: "الآفات", icon: "🐛" },
      { code: "harvest", nameAr: "الحصاد", icon: "🌾" },
      { code: "weather", nameAr: "الطقس", icon: "🌤️" },
    ],
  });
}
