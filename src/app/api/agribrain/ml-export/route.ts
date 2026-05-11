/**
 * /api/agribrain/ml-export — ML Training Data Export API
 * ======================================================
 *
 * Export intelligence snapshots and PlotDNA as ML-ready data.
 *
 * Endpoints:
 *   GET /api/agribrain/ml-export?plotId=...&format=csv     → Feature timeline CSV
 *   GET /api/agribrain/ml-export?plotId=...&format=json    → Feature timeline JSON
 *   GET /api/agribrain/ml-export?plotId=...&type=dna       → PlotDNA profile
 *   GET /api/agribrain/ml-export?plotId=...&type=snapshots → Raw snapshots (last N)
 *   GET /api/agribrain/ml-export?type=regional&lat=...&lng=...&radius=... → Regional export
 */
import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import {
  featureVectorToCSVHeaders,
  featureVectorToCSVRow,
  type MLFeatureVector,
} from "@/lib/ml-features";

export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams;
  const plotId = params.get("plotId");
  const format = params.get("format") || "json";
  const type = params.get("type") || "timeline";
  const limit = Math.min(parseInt(params.get("limit") || "365"), 1000);

  try {
    // ── PlotDNA export ──────────────────────────────────────────
    if (type === "dna") {
      if (!plotId) {
        return NextResponse.json(
          { error: "plotId is required for DNA export" },
          { status: 400 }
        );
      }
      const dna = await prisma.plotDNA.findUnique({ where: { plotId } });
      if (!dna) {
        return NextResponse.json(
          { error: "No PlotDNA found for this plot" },
          { status: 404 }
        );
      }
      return NextResponse.json({
        plotId: dna.plotId,
        location: { lat: dna.lat, lng: dna.lng },
        areaHa: dna.areaHa,
        climateZone: dna.climateZone,
        totalSnapshots: dna.totalSnapshots,
        firstSeen: dna.firstSeen,
        lastSeen: dna.lastSeen,
        ndviBaseline: dna.ndviBaseline,
        waterStressProfile: dna.waterStressProfile,
        nutrientProfile: dna.nutrientProfile,
        bioticProfile: dna.bioticProfile,
        yieldProfile: dna.yieldProfile,
        featureTimeline: dna.featureTimeline,
        seasonalSignature: dna.seasonalSignature,
        anomalyLog: dna.anomalyLog,
        spatialFingerprint: dna.spatialFingerprint,
        sourceDiversity: dna.sourceDiversity,
      });
    }

    // ── Raw snapshots export ────────────────────────────────────
    if (type === "snapshots") {
      if (!plotId) {
        return NextResponse.json(
          { error: "plotId is required" },
          { status: 400 }
        );
      }
      const snapshots = await prisma.intelligenceSnapshot.findMany({
        where: { plotId },
        orderBy: { capturedAt: "desc" },
        take: limit,
        select: {
          id: true,
          capturedAt: true,
          cropCode: true,
          cropStage: true,
          dap: true,
          mlFeatures: true,
          surfaceStats: true,
          surfaceDigest: true,
          dataAgeHrs: true,
        },
      });
      return NextResponse.json({ plotId, count: snapshots.length, snapshots });
    }

    // ── Regional export (cross-plot) ────────────────────────────
    if (type === "regional") {
      const lat = parseFloat(params.get("lat") || "0");
      const lng = parseFloat(params.get("lng") || "0");
      const radiusKm = parseFloat(params.get("radius") || "10");

      if (!lat || !lng) {
        return NextResponse.json(
          { error: "lat and lng are required for regional export" },
          { status: 400 }
        );
      }

      // Approximate degree offset for the radius
      const latDelta = radiusKm / 111.0;
      const lngDelta = radiusKm / (111.0 * Math.cos((lat * Math.PI) / 180));

      const dnas = await prisma.plotDNA.findMany({
        where: {
          lat: { gte: lat - latDelta, lte: lat + latDelta },
          lng: { gte: lng - lngDelta, lte: lng + lngDelta },
        },
        select: {
          plotId: true,
          lat: true,
          lng: true,
          areaHa: true,
          climateZone: true,
          totalSnapshots: true,
          ndviBaseline: true,
          waterStressProfile: true,
          nutrientProfile: true,
          featureTimeline: true,
        },
      });

      return NextResponse.json({
        center: { lat, lng },
        radiusKm,
        plotCount: dnas.length,
        plots: dnas,
      });
    }

    // ── Feature timeline export (default) ───────────────────────
    if (!plotId) {
      return NextResponse.json(
        { error: "plotId is required" },
        { status: 400 }
      );
    }

    const snapshots = await prisma.intelligenceSnapshot.findMany({
      where: { plotId },
      orderBy: { capturedAt: "asc" },
      take: limit,
      select: {
        capturedAt: true,
        cropCode: true,
        mlFeatures: true,
      },
    });

    if (snapshots.length === 0) {
      // Fall back to PlotDNA featureTimeline
      const dna = await prisma.plotDNA.findUnique({
        where: { plotId },
        select: { featureTimeline: true },
      });
      if (dna?.featureTimeline) {
        const timeline = dna.featureTimeline as any[];
        if (format === "csv") {
          const headers = "date," + Object.keys(timeline[0] || {}).filter(k => k !== "date").join(",");
          const rows = timeline.map((entry) => {
            const { date, ...rest } = entry;
            return `${date},${Object.values(rest).map(v => v ?? "").join(",")}`;
          });
          return new NextResponse([headers, ...rows].join("\n"), {
            headers: {
              "Content-Type": "text/csv",
              "Content-Disposition": `attachment; filename="plot_${plotId}_timeline.csv"`,
            },
          });
        }
        return NextResponse.json({ plotId, source: "plotDNA", timeline });
      }
      return NextResponse.json({ plotId, count: 0, data: [] });
    }

    // ── CSV format ──────────────────────────────────────────────
    if (format === "csv") {
      const csvHeaders = `plot_id,date,crop_code,${featureVectorToCSVHeaders()}`;
      const csvRows = snapshots.map((s) => {
        const features = s.mlFeatures as unknown as MLFeatureVector;
        return featureVectorToCSVRow(features, {
          plotId,
          date: s.capturedAt.toISOString().split("T")[0],
          cropCode: s.cropCode || "",
        });
      });

      return new NextResponse([csvHeaders, ...csvRows].join("\n"), {
        headers: {
          "Content-Type": "text/csv",
          "Content-Disposition": `attachment; filename="plot_${plotId}_ml_features.csv"`,
        },
      });
    }

    // ── JSON format (default) ───────────────────────────────────
    return NextResponse.json({
      plotId,
      count: snapshots.length,
      data: snapshots.map((s) => ({
        date: s.capturedAt.toISOString().split("T")[0],
        cropCode: s.cropCode,
        features: s.mlFeatures,
      })),
    });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Unknown error";
    console.error("[ML Export] Error:", message);
    return NextResponse.json(
      { error: `ML export failed: ${message}` },
      { status: 500 }
    );
  }
}
