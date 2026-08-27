"use client";

import React from "react";
import SpatialEngine from "./SpatialEngine";
import { buildActiveLayers } from "./LayerRegistry";

/* Backwards-compatibility exports */
export { buildActiveLayers, buildActiveLayers as buildDeckLayers };

export default function SpatialStageClient({ activeSceneId }: { activeSceneId?: string }) {
  return <SpatialEngine />;
}
