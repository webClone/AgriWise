// AgriBrain Advanced Intelligence API
import { NextRequest, NextResponse } from "next/server";
import { predictYield, estimateRevenue } from "@/lib/agribrain/yield-predictor";
import { calculateIrrigation } from "@/lib/agribrain/irrigation-optimizer";
import { calculateHarvestTiming } from "@/lib/agribrain/harvest-timer";
import { simulateScenarios, getAllScenarios } from "@/lib/agribrain/scenario-simulator";
import { generateDetailedAnalysis } from "@/lib/agribrain/crop-analyzer";

// POST - Get AI-powered agricultural insights
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { type, data } = body;

    if (!type || !data) {
      return NextResponse.json(
        { success: false, error: "نوع التحليل والبيانات مطلوبان" },
        { status: 400 }
      );
    }

    let result;

    switch (type) {
      case "yield":
        // Yield prediction
        const yieldPrediction = predictYield({
          cropCode: data.cropCode,
          plotArea: data.plotArea || 1,
          wilayaCode: data.wilayaCode || "17",
          plantDate: new Date(data.plantDate),
          irrigationType: data.irrigationType,
          soilType: data.soilType,
          fertilizerUsed: data.fertilizerUsed,
          pestControlApplied: data.pestControlApplied,
        });
        
        const revenue = estimateRevenue(
          yieldPrediction.estimatedYield, 
          data.cropCode
        );
        
        result = {
          ...yieldPrediction,
          revenue,
        };
        break;

      case "irrigation":
        // Irrigation recommendation
        result = calculateIrrigation({
          cropCode: data.cropCode,
          growthStage: data.growthStage || "vegetative",
          plotArea: data.plotArea || 1,
          soilType: data.soilType || "loamy",
          lastIrrigationDate: data.lastIrrigationDate 
            ? new Date(data.lastIrrigationDate) 
            : undefined,
          currentWeather: data.weather || {
            temperature: 25,
            humidity: 50,
            windSpeed: 10,
            precipitation: 0,
          },
        });
        break;

      case "harvest":
        // Harvest timing
        result = calculateHarvestTiming({
          cropCode: data.cropCode,
          plantDate: new Date(data.plantDate),
          growthStage: data.growthStage || "vegetative",
          weatherForecast: data.weatherForecast || [],
          marketPrices: data.marketPrices,
        });
        break;

      case "scenarios":
        // What-if scenario simulation
        result = {
          scenarios: simulateScenarios({
            cropCode: data.cropCode,
            plotArea: data.plotArea || 1,
            wilayaCode: data.wilayaCode || "17",
            currentWeather: data.weather || { temperature: 25, humidity: 50, rainfall: 0 },
            scenarios: data.selectedScenarios || ["drought", "pest_outbreak", "market_crash"],
          }),
          availableScenarios: getAllScenarios(),
        };
        break;

      case "detailed":
        // Comprehensive crop analysis
        result = generateDetailedAnalysis({
          cropCode: data.cropCode,
          wilayaCode: data.wilayaCode || "17",
          plotArea: data.plotArea || 1,
          soilType: data.soilType || "loamy",
          irrigationType: data.irrigationType || "drip",
          plantDate: new Date(data.plantDate || Date.now()),
          budget: data.budget,
          laborAvailable: data.laborAvailable,
          equipment: data.equipment,
          previousCrop: data.previousCrop,
          goals: data.goals,
        });
        break;

      default:
        return NextResponse.json(
          { success: false, error: "نوع التحليل غير صالح. الأنواع المتاحة: yield, irrigation, harvest, scenarios, detailed" },
          { status: 400 }
        );
    }

    return NextResponse.json({
      success: true,
      type,
      data: result,
    });
  } catch (error) {
    console.error("AgriBrain API error:", error);
    return NextResponse.json(
      { success: false, error: "حدث خطأ في التحليل. حاول مرة أخرى." },
      { status: 500 }
    );
  }
}

// GET - Get available analysis types and options
export async function GET() {
  return NextResponse.json({
    success: true,
    data: {
      analysisTypes: [
        { code: "yield", nameAr: "تقدير الإنتاج", description: "توقع كمية المحصول والعائد" },
        { code: "irrigation", nameAr: "الري الذكي", description: "توصيات الري المثلى" },
        { code: "harvest", nameAr: "توقيت الحصاد", description: "أفضل وقت للحصاد" },
        { code: "scenarios", nameAr: "محاكاة السيناريوهات", description: "تحليل ماذا لو" },
        { code: "detailed", nameAr: "تحليل شامل", description: "تحليل كامل للمحصول" },
      ],
      availableScenarios: getAllScenarios(),
      crops: [
        { code: "wheat", nameAr: "قمح", icon: "🌾" },
        { code: "barley", nameAr: "شعير", icon: "🌾" },
        { code: "potato", nameAr: "بطاطا", icon: "🥔" },
        { code: "tomato", nameAr: "طماطم", icon: "🍅" },
        { code: "olive", nameAr: "زيتون", icon: "🫒" },
        { code: "date", nameAr: "تمر", icon: "🌴" },
        { code: "onion", nameAr: "بصل", icon: "🧅" },
      ],
      irrigationTypes: [
        { code: "drip", nameAr: "تنقيط" },
        { code: "pivot", nameAr: "محوري" },
        { code: "sprinkler", nameAr: "رش" },
        { code: "flood", nameAr: "غمر" },
        { code: "rainfed", nameAr: "بعلي" },
      ],
      soilTypes: [
        { code: "loamy", nameAr: "طينية صفراء" },
        { code: "clay", nameAr: "طينية" },
        { code: "sandy", nameAr: "رملية" },
        { code: "rocky", nameAr: "صخرية" },
      ],
      growthStages: [
        { code: "seedling", nameAr: "شتلة" },
        { code: "vegetative", nameAr: "نمو خضري" },
        { code: "flowering", nameAr: "إزهار" },
        { code: "fruiting", nameAr: "إثمار" },
        { code: "mature", nameAr: "نضج" },
      ],
    },
  });
}
