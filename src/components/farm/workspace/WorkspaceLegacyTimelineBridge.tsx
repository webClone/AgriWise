"use client";

/**
 * P04-C03 transition bridge. The V2 map has its own native spatial host,
 * but the existing TimelineStrip still consumes PlotIntelligenceProvider.
 * Mirror only the same canonical Layer10 projection the old dashboard fed to
 * the timeline. No independent scientific acquisition or extra provider.
 * Remove this adapter when the native global timeline replaces TimelineStrip.
 */
import { useEffect } from "react";
import { useLayer10 } from "@/hooks/useLayer10";
import { usePlotIntelligence } from "@/hooks/usePlotIntelligence";
import { usePlotWorkspace } from "./PlotWorkspaceProvider";

export default function WorkspaceLegacyTimelineBridge() {
  const layer10 = useLayer10();
  const { injectData } = usePlotIntelligence();
  const { state } = usePlotWorkspace();
  const plotId = state.plotScope.plotId;
  const current = layer10.data?.plot_id === plotId;

  useEffect(() => {
    if (!current || !layer10.data) return;
    // Preservation of existing timeline is a display bridge, never a
    // scientific publication authority. A stale/uncertified reference cannot
    // promote timeline events to canonical evidence.
    const applicable = layer10.isApplicable
      && state.publication.authorityStatus === "CERTIFIED"
      && state.publication.isStale !== true;
    injectData(layer10.data, plotId, applicable);
  }, [
    current,
    layer10.data,
    layer10.isApplicable,
    plotId,
    injectData,
    state.publication.authorityStatus,
    state.publication.isStale,
  ]);

  return null;
}
