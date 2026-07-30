import { NextRequest, NextResponse } from "next/server";
import { getVisualTileFallbackStatus, resetVisualTileFallback, injectFallbackTimestamp } from "@/lib/visual-tile-fallback-registry";
import { getSession } from "@/lib/session";

export async function GET(request: NextRequest) {
  const session = await getSession();
  if (!session?.userId) {
    return NextResponse.json(
      { error: "Authentication required" },
      { status: 401 },
    );
  }
  const { searchParams } = new URL(request.url);
  const sceneId = searchParams.get("scene_id") || "";
  const reset = searchParams.get("reset") === "true";
  const injectTs = searchParams.get("test_inject_timestamp");

  if ((reset || injectTs) && process.env.NODE_ENV === "production") {
    return NextResponse.json(
      { error: "Test controls are disabled" },
      { status: 404 },
    );
  }

  if (reset) {
    resetVisualTileFallback(sceneId || null);
    return NextResponse.json({
      reset: true,
      scene_id: sceneId || null
    });
  }

  if (injectTs) {
    const ts = parseInt(injectTs, 10);
    const success = injectFallbackTimestamp(sceneId, ts);
    if (!success) {
      return NextResponse.json({
        injected: false,
        reason: "scene_not_found",
        scene_id: sceneId
      }, { status: 404 });
    }
    return NextResponse.json({
      injected: true,
      scene_id: sceneId,
      timestamp: ts
    });
  }

  const status = getVisualTileFallbackStatus(sceneId || null);
  return NextResponse.json(status);
}
