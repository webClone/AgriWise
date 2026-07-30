import { NextRequest, NextResponse } from "next/server";
import { getFAOLandIntelligence } from "@/lib/agribrain/fao-data-service";
import { generateCropSuitabilityAnalysis, CropSuitabilityResult } from "@/lib/agribrain/gemini-advisor";
import { authenticatedUserId } from "@/lib/tenant-authorization";
import { authorizePlot } from "@/lib/agribrain/authorize-plot";
import {
  getAuthoritativePlotSpatialContext,
  isValidWgs84Point,
} from "@/lib/agribrain/plot-geometry";

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
    if (!(await authenticatedUserId())) {
      return NextResponse.json(
        { error: "Authentication required" },
        { status: 401 },
      );
    }
    const body = await request.json();
    const { latitude, longitude, cropCode, plotId } = body;

    if (typeof cropCode !== "string" || !/^[a-z0-9_-]{1,64}$/i.test(cropCode)) {
      return NextResponse.json(
        { error: "A valid cropCode is required" },
        { status: 400 }
      );
    }

    let location = { lat: Number(latitude), lng: Number(longitude) };
    let authoritativePlotId: string | undefined;
    if (plotId != null) {
      if (typeof plotId !== "string" || !plotId) {
        return NextResponse.json({ error: "plotId must be a non-empty string" }, { status: 400 });
      }
      const access = await authorizePlot(plotId);
      if (!access.plot) {
        return NextResponse.json(
          { error: access.status === 401 ? "Authentication required" : "Plot not found" },
          { status: access.status },
        );
      }
      const spatial = getAuthoritativePlotSpatialContext(
        access.plot.geoJson,
        access.plot.farm.latitude,
        access.plot.farm.longitude,
      );
      if (!spatial) {
        return NextResponse.json(
          { error: "Plot has no authoritative geometry or location" },
          { status: 422 },
        );
      }
      location = spatial;
      authoritativePlotId = plotId;
    } else if (!isValidWgs84Point(location)) {
      return NextResponse.json(
        { error: "Valid latitude and longitude are required when plotId is omitted" },
        { status: 400 },
      );
    }

    // First get the FAO land intelligence profile
    const profile = await getFAOLandIntelligence(
      location.lat,
      location.lng,
      cropCode,
      authoritativePlotId,
    );

    // Get crop name
    const cropName = CROP_NAMES[cropCode] || cropCode;

    // Generate AI-powered suitability analysis
    console.log("[Suitability API] Calling AI analysis for:", cropCode, "at authorized location");
    
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
      // v5.1: landSuitability may be null (mock data removed)
      if (profile.landSuitability) {
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
      } else {
        return NextResponse.json({
          success: true,
          source: "not_available",
          analysis: {
            suitabilityScore: null,
            suitabilityClass: null,
            potentialYieldRainfed: null,
            potentialYieldIrrigated: null,
            limitingFactors: [],
            recommendations: ["Suitability data not available. Use /api/agribrain/crop-suitability for Python engine results."],
            confidence: "Not available",
            reasoning: "v5.1: Frontend suitability calculator removed. Use Python CropSuitabilityEngine."
          }
        });
      }
    }
  } catch (error) {
    console.error("Suitability analysis error:", error);
    return NextResponse.json(
      { error: "Failed to analyze crop suitability", details: String(error) },
      { status: 500 }
    );
  }
}
