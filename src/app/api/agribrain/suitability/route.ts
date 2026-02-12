import { NextRequest, NextResponse } from "next/server";
import { getFAOLandIntelligence } from "@/lib/agribrain/fao-data-service";
import { generateCropSuitabilityAnalysis, CropSuitabilityResult } from "@/lib/agribrain/gemini-advisor";

// Crop name mapping
const CROP_NAMES: Record<string, string> = {
  wheat: "Wheat",
  barley: "Barley",
  potato: "Potato",
  tomato: "Tomato",
  olive: "Olive",
  date: "Date Palm",
  onion: "Onion",
  chickpea: "Chickpea",
  lentil: "Lentil",
  watermelon: "Watermelon"
};

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { latitude, longitude, cropCode } = body;

    if (!latitude || !longitude || !cropCode) {
      return NextResponse.json(
        { error: "Missing required fields: latitude, longitude, cropCode" },
        { status: 400 }
      );
    }

    // First get the FAO land intelligence profile
    const profile = await getFAOLandIntelligence(latitude, longitude, cropCode);

    // Get crop name
    const cropName = CROP_NAMES[cropCode] || cropCode;

    // Generate AI-powered suitability analysis
    console.log("[Suitability API] Calling AI analysis for:", cropCode, "at", latitude, longitude);
    
    let aiAnalysis = null;
    try {
      aiAnalysis = await generateCropSuitabilityAnalysis(profile, cropCode, cropName);
      console.log("[Suitability API] AI result:", aiAnalysis ? "SUCCESS" : "NULL");
    } catch (aiError) {
      console.error("[Suitability API] AI call error:", aiError);
    }

    if (aiAnalysis) {
      return NextResponse.json({
        success: true,
        source: "ai",
        analysis: aiAnalysis
      });
    } else {
      // Fallback to basic calculation if AI fails
      return NextResponse.json({
        success: true,
        source: "fallback",
        analysis: {
          suitabilityScore: profile.landSuitability.gaezScore,
          suitabilityClass: profile.landSuitability.suitabilityClass,
          potentialYieldRainfed: profile.landSuitability.potentialYield,
          potentialYieldIrrigated: profile.landSuitability.attainableYield,
          limitingFactors: profile.landSuitability.limitingFactors,
          recommendations: ["Enable AI analysis for detailed recommendations"],
          confidence: "Low",
          reasoning: "Using basic calculation. AI service unavailable."
        } as CropSuitabilityResult
      });
    }
  } catch (error) {
    console.error("Suitability analysis error:", error);
    return NextResponse.json(
      { error: "Failed to analyze crop suitability", details: String(error) },
      { status: 500 }
    );
  }
}
