/** P04 Candidate 02: display gating only. Never grants publication or hardware authority. */
export const P04_INVESTIGATION_KINDS = Object.freeze(["water", "compare", "simulate"]);
export const P04_HOST_MODES = Object.freeze(["context", "split", "workbench"]);

export function evaluateZoneInvestigationContext({
  workspace,
  layer10PlotId,
  layer10SelectedZoneId,
  layer10PublicationId,
  assessmentPublicationId,
  assessmentSnapshotId,
  assessmentReady,
  assessmentApplicable,
}) {
  const currentPlot = workspace?.plotScope?.plotId;
  const selected = workspace?.selectedEntity;
  const zoneId = selected?.kind === "ZONE" && typeof selected.id === "string" ? selected.id : null;
  const samePlot = Boolean(currentPlot && layer10PlotId === currentPlot);
  const matchingSelection = samePlot && Boolean(zoneId) && layer10SelectedZoneId === zoneId;
  const currentSnapshot = Boolean(
    matchingSelection && selected.sourceSnapshotId &&
    selected.sourceSnapshotId === workspace?.publication?.snapshotId
  );
  const matchingScientificPublication = Boolean(
    layer10PublicationId && assessmentPublicationId &&
    layer10PublicationId === assessmentPublicationId
  );
  const qualified = Boolean(
    currentSnapshot && assessmentReady && assessmentApplicable &&
    workspace?.publication?.authorityStatus === "CERTIFIED" &&
    workspace?.publication?.isStale !== true &&
    assessmentSnapshotId === workspace?.publication?.snapshotId &&
    matchingScientificPublication
  );
  return {
    zoneId: matchingSelection ? zoneId : null,
    currentSnapshot,
    qualified,
    canShowZoneNumbers: qualified,
    explanation: !matchingSelection
      ? "Select a zone on this plot to investigate."
      : qualified
        ? "Current qualified publication and selected zone agree."
        : "Selected zone is available for exploration, but scientific values are not qualified for this exact plot, publication and time.",
  };
}
