export type VisualTileFallbackState = {
  fallbackUsed: boolean;
  lastReason: string | null;
  lastTimestamp: number;
  provider?: string | null;
  tile?: string | null;
  sceneId?: string | null;
};

const globalForVisualTile = globalThis as unknown as {
  visualTileFallbackRegistryMap: Record<string, VisualTileFallbackState>;
};

if (!globalForVisualTile.visualTileFallbackRegistryMap) {
  globalForVisualTile.visualTileFallbackRegistryMap = {};
}

export const visualTileFallbackRegistryMap = globalForVisualTile.visualTileFallbackRegistryMap;

const TTL_MS = 5 * 60 * 1000; // 5 minutes TTL

function getRegistryKey(sceneId?: string | null, provider?: string | null, tile?: string | null): string {
  if (sceneId) return sceneId;
  if (provider && tile) return `${provider}_${tile}`;
  return "default";
}

export function recordVisualTileFallback(
  reason: string,
  provider?: string | null,
  tile?: string | null,
  sceneId?: string | null
) {
  const key = getRegistryKey(sceneId, provider, tile);
  visualTileFallbackRegistryMap[key] = {
    fallbackUsed: true,
    lastReason: reason,
    lastTimestamp: Date.now(),
    provider: provider ?? null,
    tile: tile ?? null,
    sceneId: sceneId ?? null,
  };
}

export function resetVisualTileFallback(sceneId?: string | null) {
  const key = getRegistryKey(sceneId);
  delete visualTileFallbackRegistryMap[key];
}

export function getVisualTileFallbackStatus(sceneId?: string | null) {
  const key = getRegistryKey(sceneId);
  const state = visualTileFallbackRegistryMap[key];
  if (!state) {
    return {
      scene_id: sceneId || null,
      fallback_used: false,
      active: false,
      reason: null,
      provider: null,
      tile: null,
      timestamp: 0,
      ttl_ms: TTL_MS,
    };
  }

  const now = Date.now();
  const active = state.fallbackUsed && (now - state.lastTimestamp < TTL_MS);

  return {
    scene_id: state.sceneId || sceneId || null,
    fallback_used: state.fallbackUsed,
    active,
    reason: state.lastReason,
    provider: state.provider,
    tile: state.tile,
    timestamp: state.lastTimestamp,
    ttl_ms: TTL_MS,
  };
}

// Helper for testing to inject custom timestamps for TTL logic verification
export function injectFallbackTimestamp(sceneId: string, timestamp: number): boolean {
  const state = visualTileFallbackRegistryMap[sceneId];
  if (!state) return false;
  state.lastTimestamp = timestamp;
  return true;
}
