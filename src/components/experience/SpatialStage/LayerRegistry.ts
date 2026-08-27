import { GeoJsonLayer, BitmapLayer } from "@deck.gl/layers";
import { LineageLayer } from "./LineageLayer";
import type { ResolvedShotState } from "./ShotDirector";
import { ILLUSTRATIVE_WORLD, PREPARED_WORLD } from "../world/selectors";
import opticalMeta from "../world/demo-optical.meta.json";
import farmMeta from "../world/farm-wide.meta.json";
import orgMeta from "../world/organization-atmosphere.meta.json";
import regionMeta from "../world/region-atmosphere.meta.json";
import nationMeta from "../world/nation-atmosphere.meta.json";

/* ═══ AgriWise Multi-Stage LayerRegistry ═════════════════════════
   Deck.gl Layer Composition driven by fine-grained behavior channels
   and stage-specific visual assets with exact Mercator alignment.
   
   Stage Visual Asset Architecture:
   1. Field: /r2/hero-field-master.webp (Exact parcel alignment)
   2. Farm: /r2/farm-wide.webp (Wide landscape context)
   3. Organization: /r2/organization-atmosphere.webp (Valley plain & Atlas mountains)
   4. Region: /r2/region-atmosphere.webp (Stratospheric basin & coast)
   5. Nation: /r2/nation-atmosphere.webp (Orbital sovereign environment)
   ═══════════════════════════════════════════════════════════════ */

export function buildActiveLayers(state: ResolvedShotState): any[] {
  const { channels } = state;
  const layers: any[] = [];

  const neutralSlate: [number, number, number] = [148, 163, 184];
  const darkSlate: [number, number, number] = [51, 65, 85];

  // ── 1. Stage-Specific Raster Background Layers ──────────────
  // Field Master Optical Aerial
  if (channels.opticalField > 0.02) {
    layers.push(
      new BitmapLayer({
        id: "stage-raster-field",
        bounds: opticalMeta.bounds as [number, number, number, number],
        image: "/r2/hero-field-master.webp",
        opacity: channels.opticalField,
      })
    );
  }

  // Farm-Wide Optical Orthomosaic (Exact wide context bounds)
  if (channels.opticalFarm > 0.02) {
    layers.push(
      new BitmapLayer({
        id: "stage-raster-farm",
        bounds: (farmMeta.bounds || opticalMeta.bounds) as [number, number, number, number],
        image: "/r2/farm-wide.webp",
        opacity: channels.opticalFarm,
      })
    );
  }

  // Organization Atmospheric Landscape (Mitidja Valley & Atlas foothills)
  if (channels.opticalOrg > 0.02) {
    layers.push(
      new BitmapLayer({
        id: "stage-raster-org",
        bounds: (orgMeta.bounds || [2.75, 36.25, 3.45, 36.75]) as [number, number, number, number],
        image: "/r2/organization-atmosphere.webp",
        opacity: channels.opticalOrg,
      })
    );
  }

  // Regional High-Altitude Stratospheric View
  if (channels.opticalRegion > 0.02) {
    layers.push(
      new BitmapLayer({
        id: "stage-raster-region",
        bounds: (regionMeta.bounds || [1.2, 34.8, 5.8, 37.8]) as [number, number, number, number],
        image: "/r2/region-atmosphere.webp",
        opacity: channels.opticalRegion,
      })
    );
  }

  // Sovereign Orbital Environment
  if (channels.opticalNation > 0.02) {
    layers.push(
      new BitmapLayer({
        id: "stage-raster-nation",
        bounds: (nationMeta.bounds || [-9.0, 18.0, 14.0, 38.5]) as [number, number, number, number],
        image: "/r2/nation-atmosphere.webp",
        opacity: channels.opticalNation,
      })
    );
  }


  // ── 2. Sister Farms Context Envelopes ───────────────────────
  if (channels.sisterFarms > 0.02) {
    const sisterFarmFeatures = ILLUSTRATIVE_WORLD.farms
      .filter((f) => f.id !== "FARM-04")
      .map((f) => {
        const prep = PREPARED_WORLD.preparedFarms.get(f.id);
        return {
          type: "Feature",
          properties: { id: f.id },
          geometry: { type: "Polygon", coordinates: [prep?.hullCoordinates || []] },
        };
      });

    layers.push(
      new GeoJsonLayer({
        id: "sister-farms",
        data: { type: "FeatureCollection", features: sisterFarmFeatures } as any,
        filled: true,
        stroked: true,
        getFillColor: [...darkSlate, Math.round(12 * channels.sisterFarms)],
        getLineColor: [...neutralSlate, Math.round(90 * channels.sisterFarms)],
        getLineWidth: 1.4,
        lineWidthMinPixels: 1.0,
      })
    );
  }

  // ── 3. Peer Regional Context Areas (Biskra, Guelma, Chlef) ──
  if (channels.peerRegions > 0.02) {
    const peerRegionFeatures = ILLUSTRATIVE_WORLD.regions
      .filter((r) => r.id !== "REGION-MITIDJA")
      .map((r) => ({
        type: "Feature",
        properties: { id: r.id, name: r.name },
        geometry: { type: "Polygon", coordinates: [r.coordinates] },
      }));

    layers.push(
      new GeoJsonLayer({
        id: "peer-regions",
        data: { type: "FeatureCollection", features: peerRegionFeatures } as any,
        filled: true,
        stroked: true,
        getFillColor: [...darkSlate, Math.round(16 * channels.peerRegions)],
        getLineColor: [...neutralSlate, Math.round(90 * channels.peerRegions)],
        getLineWidth: 1.4,
        lineWidthMinPixels: 1.0,
      })
    );
  }

  // ── 4. Dedicated Progressive LineageLayer ───────────────────
  layers.push(
    new LineageLayer({
      id: "active-lineage",
      selectedPlotId: state.selectedPlotId,
      channels,
      opacity: 1.0,
    })
  );

  return layers;
}

export const buildDeckLayers = buildActiveLayers;
