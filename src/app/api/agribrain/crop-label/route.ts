/**
 * /api/agribrain/crop-label — Crop Label proxy endpoint
 *
 * Proxies confirmed crop labels from the UI to the agribrain backend.
 */
import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/session";
import { authorizePlot } from "@/lib/agribrain/authorize-plot";
import { buildSignedInternalHeaders } from "@/lib/agribrain/internal-service-auth";
import { normalizeCropRuntimeDeclarationReceipt } from "@/lib/agribrain/crop-runtime-declaration.mjs";

export async function POST(request: NextRequest) {
  try {
    const session = await getSession();
    const userId = session?.userId || null;
    const body = await request.json();

    const {
      plotId,
      cropCode,
      notes,
    } = body;

    if (!plotId || !cropCode) {
      return NextResponse.json(
        { error: "plotId and cropCode are required" },
        { status: 400 }
      );
    }
    if (!userId) {
      return NextResponse.json(
        { error: "Authentication required" },
        { status: 401 },
      );
    }
    const access = await authorizePlot(plotId);
    if (!access.plot) {
      return NextResponse.json(
        { error: "Plot not found" },
        { status: access.status },
      );
    }

    const apiUrl = process.env.AGRIBRAIN_API_URL || "http://127.0.0.1:8000";

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 15_000);

    const upstreamPath = "/v2/crop-label";
    const upstreamBody = JSON.stringify({
      plot_id: plotId,
      crop_code: cropCode,
      // Identity confirmation does not assert a crop-cycle date. Planting and
      // harvest dates require their own explicit, typed crop-cycle workflow.
      planting_date: null,
      harvest_date: null,
      // The backend derives label authority from the authenticated namespace.
      // A browser cannot promote itself to an admin/agronomist source.
      label_source: "farmer_confirmed",
      notes: notes || null,
      synthetic: false,
    });
    const signedHeaders = buildSignedInternalHeaders(
      "POST",
      upstreamPath,
      {
        tenantId: String(userId),
        farmId: String(access.plot.farmId),
        plotId: String(plotId),
      },
      upstreamBody,
    );

    const response = await fetch(`${apiUrl}${upstreamPath}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...signedHeaders },
      body: upstreamBody,
      signal: controller.signal,
    }).finally(() => clearTimeout(timeoutId));

    if (!response.ok) {
      const errorText = await response.text();
      console.error(`[CropLabel Proxy API] Error: ${response.status} - ${errorText}`);
      return NextResponse.json(
        { success: false, error: `Crop label creation failed: ${response.statusText}` },
        { status: response.status }
      );
    }

    const result = await response.json();
    let runtimeDeclaration;
    try {
      runtimeDeclaration = normalizeCropRuntimeDeclarationReceipt(
        result?.runtime_declaration,
        {
          tenant_id: String(userId),
          farm_id: String(access.plot.farmId),
          plot_id: String(plotId),
        },
      );
      const requestedCropCode = String(cropCode).trim().toLowerCase()
        .replace(/[- ]/g, "_");
      if (
        runtimeDeclaration.crop_code !== requestedCropCode
        || runtimeDeclaration.authority !== "FARMER_CONFIRMED"
        || runtimeDeclaration.source !== "authenticated_farmer_crop_identity"
      ) {
        throw new Error("runtime crop declaration authority mismatch");
      }
    } catch (receiptError) {
      const reason = receiptError instanceof Error
        ? receiptError.message
        : "invalid runtime declaration receipt";
      console.error(`[CropLabel Proxy API] ${reason}`);
      return NextResponse.json(
        {
          success: false,
          error: "Crop declaration was not confirmed by canonical runtime state",
        },
        { status: 502 },
      );
    }
    return NextResponse.json({
      ...result,
      success: true,
      runtime_declaration: runtimeDeclaration,
    });

  } catch (error: unknown) {
    if (error instanceof Error && error.name === "AbortError") {
      return NextResponse.json(
        { success: false, error: "Crop label creation timed out" },
        { status: 504 }
      );
    }
    const message = error instanceof Error ? error.message : "Unknown error";
    console.error("[CropLabel Proxy API] Error:", message);
    return NextResponse.json(
      { success: false, error: `Crop label creation failed: ${message}` },
      { status: 500 }
    );
  }
}
