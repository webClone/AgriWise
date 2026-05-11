/**
 * /api/agribrain/satellite-tile-save/[plotId] — Save satellite tile + LLM observation
 *
 * Called after LLM vision analyzes the satellite tile.
 * Saves the tile as a PlotPhoto with the vision observation embedded
 * as notes and AI tags — so you see both the image and the LLM's
 * assessment in the photo gallery.
 *
 * Deduplicates: only one satellite photo per plot (replaces the old one).
 */
import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { revalidatePath } from "next/cache";

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ plotId: string }> }
) {
  const { plotId } = await params;
  try {
    const body = await request.json().catch(() => ({}));
    const tileDate = body.fetched_date ? new Date(body.fetched_date) : new Date();

    // Vision analysis results (from LLM)
    const vision = body.vision || null;

    // Build notes from LLM observation
    let notes = "Sentinel-2 L2A True Color — Auto-captured by AgriBrain";
    const aiTags: string[] = ["sentinel-2", "rgb", "satellite", "auto-captured"];

    if (vision) {
      const parts: string[] = [];
      if (vision.estimated_crop_type) parts.push(`Crop: ${vision.estimated_crop_type}`);
      if (vision.emergence_stage) parts.push(`Stage: ${vision.emergence_stage}`);
      if (vision.vegetation_pct != null) parts.push(`Vegetation: ${vision.vegetation_pct}%`);
      if (vision.bare_soil_pct != null) parts.push(`Bare Soil: ${vision.bare_soil_pct}%`);
      if (vision.crop_rows_detected) parts.push("Crop rows detected ✓");
      if (vision.weed_pressure) parts.push(`Weed pressure: ${vision.weed_pressure}`);
      if (vision.field_uniformity) parts.push(`Uniformity: ${vision.field_uniformity}`);
      if (vision.irrigation_visible) parts.push("Irrigation visible ✓");
      if (vision.explanation) parts.push(`\n${vision.explanation}`);

      notes = `🛰️ AgriBrain Vision Observation\n${parts.join(" • ")}`;

      // Add semantic AI tags
      if (vision.estimated_crop_type) aiTags.push(vision.estimated_crop_type.toLowerCase());
      if (vision.emergence_stage) aiTags.push(vision.emergence_stage);
      if (vision.crop_rows_detected) aiTags.push("crop-rows");
      if (vision.weed_pressure && vision.weed_pressure !== "none") aiTags.push("weed-pressure");
    }

    const imageUrl = `/api/agribrain/satellite-tile-image/${plotId}`;

    // Remove old satellite photos for this plot
    try {
      await prisma.plotPhoto.deleteMany({
        where: { plotId, source: "satellite" },
      });
    } catch (e) {
      console.warn("[Satellite Save] Cleanup failed:", e);
    }

    // Create the photo + observation record
    const photo = await prisma.plotPhoto.create({
      data: {
        plotId,
        url: imageUrl,
        type: "OVERVIEW",  // Use OVERVIEW until SATELLITE enum is generated
        date: tileDate,
        tags: ["sentinel-2", "satellite", "auto"],
        notes,
        source: "satellite",
        aiTags,
        aiConfidence: vision?.confidence ?? 0.95,
        isProcessed: !!vision,
      },
    });

    // Revalidate
    revalidatePath(`/farm/[id]/plot/${plotId}/user-inputs`);

    return NextResponse.json({
      success: true,
      photo_id: photo.id,
      has_vision: !!vision,
      message: vision
        ? "Satellite tile + LLM observation saved"
        : "Satellite tile saved (no vision analysis)",
    });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Unknown error";
    console.error("[Satellite Save] Error:", message);
    return NextResponse.json(
      { success: false, error: message },
      { status: 500 }
    );
  }
}
