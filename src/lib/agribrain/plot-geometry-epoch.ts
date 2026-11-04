/** Server-only B2B-05 geometry writes. Never use client tenant/farm claims. */
import "server-only";
import { buildSignedInternalHeaders } from "./internal-service-auth";

export type PlotGeometryOwnership = {
  id: string;
  farmId: string;
  geometryVersion: number | null;
  geometryHash: string | null;
  geoJson: unknown;
};

export type GeometryEpochReceipt = {
  plot_id: string;
  tenant_id: string;
  geometry_version: number;
  geometry_hash: string;
  previous_scope_hash: string;
  scope_hash: string;
  invalidated_cache_entries: number;
  cache_invalidation_attempted: boolean;
  authority: "plot_geometry_epoch_only";
};

async function callGeometryEpoch(
  method: "POST" | "PUT",
  plotId: string,
  farmId: string,
  userId: string,
  payload: Record<string, unknown>,
): Promise<GeometryEpochReceipt> {
  const path = "/v2/b2b05/plots/" + plotId + "/geometry"
    + (method === "POST" ? "/initialize" : "");
  const base = (process.env.PYTHON_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
  const bodyText = JSON.stringify(payload);
  const headers = buildSignedInternalHeaders(
    method, path, { tenantId: userId, farmId, plotId }, bodyText,
  );
  const response = await fetch(base + path, {
    method, headers: { ...headers, "Content-Type": "application/json" },
    body: bodyText, cache: "no-store",
  });
  if (!response.ok) {
    throw new Error("plot_geometry_epoch_write_failed:" + response.status);
  }
  const receipt = (await response.json()) as GeometryEpochReceipt;
  if (
    receipt.plot_id !== plotId || receipt.tenant_id !== userId
    || !Number.isInteger(receipt.geometry_version)
    || typeof receipt.geometry_hash !== "string"
  ) {
    throw new Error("plot_geometry_epoch_receipt_invalid");
  }
  return receipt;
}

export async function initializePlotGeometry(
  plotId: string, farmId: string, authenticatedUserId: string, geoJson: unknown,
): Promise<GeometryEpochReceipt> {
  return callGeometryEpoch("POST", plotId, farmId, authenticatedUserId, {
    geo_json: geoJson,
  });
}

export async function updatePlotGeometry(
  ownedPlot: PlotGeometryOwnership,
  authenticatedUserId: string,
  geoJson: unknown,
): Promise<GeometryEpochReceipt> {
  if (
    ownedPlot.geometryVersion == null
    || !Number.isInteger(ownedPlot.geometryVersion)
    || ownedPlot.geometryVersion < 1
    || !ownedPlot.geometryHash
  ) {
    if (ownedPlot.geoJson != null) {
      throw new Error("plot_geometry_epoch_uninitialized_requires_backfill");
    }
    return initializePlotGeometry(
      ownedPlot.id, ownedPlot.farmId, authenticatedUserId, geoJson,
    );
  }
  return callGeometryEpoch(
    "PUT", ownedPlot.id, ownedPlot.farmId, authenticatedUserId,
    {
      geo_json: geoJson,
      expected_geometry_version: ownedPlot.geometryVersion,
      expected_geometry_hash: ownedPlot.geometryHash,
    },
  );
}
