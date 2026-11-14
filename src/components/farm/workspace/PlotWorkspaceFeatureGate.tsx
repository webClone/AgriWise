/**
 * P02 transition gate. The default path is deliberately the exact legacy
 * PlotDashboard component; neither it nor the scientific providers are
 * re-mounted in the disabled path.
 *
 * Server-side feature selection prevents a client hydration switch from
 * mounting competing maps/publication providers.
 */
import PlotDashboard from "@/components/farm/PlotDashboard";
import PlotWorkspaceShell from "./PlotWorkspaceShell";

export interface PlotWorkspaceProps {
  farm: Record<string, unknown> | null;
  plot: Record<string, unknown> | null;
  cropName?: string;
  context: Record<string, unknown> | null;
  plotId?: string;
  farmId?: string;
}

export const isPlotWorkspaceV2Enabled = () =>
  process.env.NEXT_PUBLIC_PLOT_WORKSPACE_V2 === "true";

export default function PlotWorkspaceFeatureGate(props: PlotWorkspaceProps) {
  if (!isPlotWorkspaceV2Enabled()) return <PlotDashboard {...props} />;
  return <PlotWorkspaceShell {...props} />;
}
