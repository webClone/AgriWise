import { NextRequest } from "next/server";
import { recordVisualTileFallback } from "@/lib/visual-tile-fallback-registry";
import {
  isRasterImagePayload,
  transparentRasterTile,
} from "@/lib/raster-tile-response";
import { authenticatedUserId } from "@/lib/tenant-authorization";

const ALLOWED_PROVIDERS = new Set(["cbers", "sentinel", "landsat", "local_synthetic"]);
const MAX_TILE_BYTES = 10 * 1024 * 1024;

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function parseTileCoordinate(value: string): number | null {
  if (!/^\d+$/.test(value)) return null;
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) ? parsed : null;
}

function allowedRedirectUrl(location: string): URL | null {
  try {
    const configured = new URL(process.env.TITILER_BASE_URL || "https://titiler.xyz");
    const candidate = new URL(location);
    if (candidate.origin !== configured.origin) return null;
    if (!/^https?:$/.test(candidate.protocol) || candidate.username || candidate.password) return null;
    return candidate;
  } catch {
    return null;
  }
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ provider: string; z: string; x: string; y: string }> }
) {
  if (!(await authenticatedUserId())) {
    return new Response(null, {
      status: 401,
      headers: { "Cache-Control": "no-store" },
    });
  }
  const { provider, z, x, y } = await params;
  const { searchParams } = new URL(request.url);
  const sceneId = searchParams.get("scene_id") || "";
  const tileStr = `${z}/${x}/${y}`;

  const zoom = parseTileCoordinate(z);
  const tileX = parseTileCoordinate(x);
  const tileY = parseTileCoordinate(y);
  const tileLimit = zoom == null || zoom > 22 ? 0 : 2 ** zoom;
  if (
    !ALLOWED_PROVIDERS.has(provider)
    || zoom == null
    || tileX == null
    || tileY == null
    || tileX >= tileLimit
    || tileY >= tileLimit
    || (sceneId && !/^[A-Za-z0-9._:-]{1,256}$/.test(sceneId))
  ) {
    return new Response(null, {
      status: 400,
      headers: { "Cache-Control": "no-store" },
    });
  }

  try {
    const apiUrl = process.env.AGRIBRAIN_API_URL || "http://127.0.0.1:8000";
    const targetUrl = `${apiUrl}/v2/visual-tile/${provider}/${z}/${x}/${y}?scene_id=${encodeURIComponent(sceneId)}`;

    // Use manual redirect mode to intercept FastAPI 302 Redirect Responses
    const res = await fetch(targetUrl, {
      redirect: "manual",
      signal: AbortSignal.timeout(15_000),
    });
    
    if (res.status === 302 || res.status === 307 || res.status === 301) {
      const location = res.headers.get("location");
      if (location) {
        const safeLocation = allowedRedirectUrl(location);
        if (!safeLocation) {
          recordVisualTileFallback(
            "Redirect target was not on the configured tile origin",
            provider,
            tileStr,
            sceneId,
          );
          return transparentRasterTile("visual-proxy-transparent-fallback", "redirect_origin_rejected");
        }
        // Fetch the tile server-side instead of redirecting the browser
        // This prevents the browser from making direct external requests
        try {
          const tileRes = await fetch(safeLocation, {
            redirect: "error",
            signal: AbortSignal.timeout(15_000),
          });
          if (tileRes.ok) {
            const advertisedLength = Number(tileRes.headers.get("Content-Length"));
            if (Number.isFinite(advertisedLength) && advertisedLength > MAX_TILE_BYTES) {
              throw new Error("Redirect tile exceeds maximum response size");
            }
            const buffer = await tileRes.arrayBuffer();
            if (buffer.byteLength > MAX_TILE_BYTES) {
              throw new Error("Redirect tile exceeds maximum response size");
            }
            const contentType = tileRes.headers.get("Content-Type");
            if (isRasterImagePayload(buffer, contentType)) {
              return new Response(buffer, {
                headers: {
                  "Content-Type": contentType || "image/png",
                  "Cache-Control": "private, max-age=86400, stale-while-revalidate=604800",
                  "X-Tile-Source": "visual-proxy",
                },
              });
            }
            console.warn("[Visual Tile Proxy] Redirect target returned a non-image payload");
            recordVisualTileFallback(
              "Redirect target returned a non-image payload",
              provider,
              tileStr,
              sceneId
            );
          } else {
            console.warn(`[Visual Tile Proxy] Redirected tile request failed with status ${tileRes.status}`);
            recordVisualTileFallback(
              `Failed to fetch tile from redirected URL (status: ${tileRes.status})`,
              provider,
              tileStr,
              sceneId
            );
          }
        } catch (err: unknown) {
          console.error("[Visual Tile Proxy] Redirected tile request failed", err);
          recordVisualTileFallback(
            `Error fetching tile from redirected URL: ${errorMessage(err)}`,
            provider,
            tileStr,
            sceneId
          );
        }
      } else {
        recordVisualTileFallback(
          "Redirect response did not contain location header",
          provider,
          tileStr,
          sceneId
        );
      }

      // If redirect fetching failed, return transparent PNG fallback
      return transparentRasterTile("visual-proxy-transparent-fallback", "redirect_fetch_failed");
    }

    if (!res.ok) {
      console.warn(`[Visual Tile Proxy] FastAPI returned non-OK status: ${res.status} ${res.statusText}`);
      recordVisualTileFallback(
        `FastAPI returned non-OK status: ${res.status} ${res.statusText}`,
        provider,
        tileStr,
        sceneId
      );
      return transparentRasterTile("visual-proxy-transparent-fallback", `upstream_http_${res.status}`);
    }

    const imageBuffer = await res.arrayBuffer();
    const imageContentType = res.headers.get("Content-Type");
    if (!isRasterImagePayload(imageBuffer, imageContentType)) {
      recordVisualTileFallback(
        "FastAPI returned a non-image tile payload",
        provider,
        tileStr,
        sceneId
      );
      return transparentRasterTile("visual-proxy-transparent-fallback", "invalid_upstream_image");
    }

    if (sceneId === "CB4A_WPM_20260109" || sceneId.startsWith("synthetic_")) {
      return new Response(imageBuffer, {
        headers: {
          "Content-Type": imageContentType || "image/png",
          "Cache-Control": "no-store, max-age=0",
          "X-Tile-Source": "visual-proxy-mock-or-fallback"
        }
      });
    }

    // Real satellite tiles are cached for 24h in production, no-cache in development
    const cacheHeader = process.env.NODE_ENV === "development"
      ? "no-store, no-cache, must-revalidate, proxy-revalidate"
      : "private, max-age=86400";

    return new Response(imageBuffer, {
      headers: {
        "Content-Type": imageContentType || "image/png",
        "Cache-Control": cacheHeader
      }
    });
  } catch (error: unknown) {
    console.error("[Visual Tile Proxy Error]", error);
    recordVisualTileFallback(
      `Internal Proxy Error: ${errorMessage(error)}`,
      provider,
      tileStr,
      sceneId
    );
    // Return transparent PNG even on hard network/server errors to prevent frontend crashes
    return transparentRasterTile("visual-proxy-transparent-fallback", "proxy_error");
  }
}
