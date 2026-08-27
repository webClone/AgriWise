/* ═══ AgriWise R2 Pass 3B — Marketing Telemetry Dispatcher ═════
   Lean once-per-pageview milestone events. Zero map coordinates,
   zero agricultural telemetry, zero user surveillance.
   ═══════════════════════════════════════════════════════════════ */

export type MarketingEvent =
  | "hero_view"
  | "hero_farmer_cta"
  | "hero_org_cta"
  | "scale_field_reached"
  | "scale_farm_reached"
  | "scale_organization_reached"
  | "scale_region_reached"
  | "scale_nation_reached"
  | "scale_completed";

const firedEvents = new Set<string>();

export function emitMarketingEvent(event: MarketingEvent): void {
  if (firedEvents.has(event)) return; // Once per pageview milestone
  firedEvents.add(event);

  if (typeof window !== "undefined" && process.env.NODE_ENV === "development") {
    console.log(`[AgriWise Marketing Telemetry] Event emitted: ${event}`);
  }

  // Dispatch custom browser DOM event for analytics hooks
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent("agriwise_marketing_event", { detail: { event, timestamp: Date.now() } }));
  }
}
