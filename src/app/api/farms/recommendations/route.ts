import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { cropCode, growthStage, soilType, region } = body;

    if (!cropCode) {
      return NextResponse.json(
        { error: "Missing cropCode" },
        { status: 400 }
      );
    }

    // 1. Fetch Crop Reference Data
    const cropData = await prisma.crop.findUnique({
      where: { code: cropCode },
    });

    if (!cropData) {
      return NextResponse.json(
        { error: "Crop data not found" },
        { status: 404 }
      );
    }

    // 2. Generate Recommendations based on inputs
    const recommendations = [];

    // Soil Compatibility
    if (soilType && cropData.soilPreferences) {
      const isSuitable = cropData.soilPreferences.includes(soilType);
      if (isSuitable) {
        recommendations.push({
          type: "soil",
          status: "success",
          message: `Succès : Le sol ${soilType} est bien adapté pour ${cropData.nameFr}.`,
        });
      } else {
        recommendations.push({
          type: "soil",
          status: "warning",
          message: `Attention : ${cropData.nameFr} préfère les sols ${cropData.soilPreferences.join(", ")}.`,
        });
      }
    }

    // Growth Stage Advice
    if (growthStage && cropData.stages) {
      const stages = cropData.stages as any[];
      const currentStage = stages.find((s) => s.stage === growthStage);
      
      if (currentStage) {
        recommendations.push({
          type: "stage",
          status: "info",
          message: `Stade actuel : ${currentStage.nameAr || growthStage}.`,
          tasks: currentStage.tasks || [],
        });
      }
    }

    // Water Requirements
    if (cropData.waterRequirements) {
      const waterReqs = cropData.waterRequirements as any;
      // Simple logic: mapping stage to requirement if possible
      // This can be made more sophisticated
      recommendations.push({
        type: "water",
        status: "info",
        message: `Besoins en eau : ${JSON.stringify(waterReqs)}`,
      });
    }

    // Seasonality Check
    if (region && cropData.seasonality) {
      // Determine if currently in planting season
      // This requires current month and region mapping
      // Placeholder logic
    }

    return NextResponse.json({
      success: true,
      crop: {
        nameAr: cropData.nameAr,
        nameFr: cropData.nameFr,
        icon: cropData.icon,
      },
      recommendations,
      data: cropData, // Return full data for frontend to use
    });

  } catch (error) {
    console.error("Error generating recommendations:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
