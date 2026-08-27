import { CompositeLayer } from "@deck.gl/core";
import { GeoJsonLayer, ScatterplotLayer, PathLayer } from "@deck.gl/layers";
import {
  selectPlotLineage,
  selectPreparedEntity,
  slicePathByProgress,
  ILLUSTRATIVE_WORLD,
  PREPARED_WORLD,
} from "../world/selectors";
import regionalDensityGeojson from "../world/demo-regional-density.json";
import type { VisualChannelProfile } from "./ShotDirector";

/* ═══ AgriWise Cinematic LineageLayer ═══════════════════════════
   Feature-by-Feature Lineage, Micro-Interaction Cues, Distributed
   Organization Topology, Deterministic Regional Density & Sovereign Nation.
   
   Architecture:
   1. Active lineage strictly uses AgriWise green (#4ade80).
   2. Restrained line weights (1.8px settled, 2.2px acquisition).
   3. Subtle fill (4-6% max) preserving high-res crop textures.
   4. Micro corner ticks on PLOT-017 vertices.
   5. Distributed topology for Organization (no huge glowing dots).
   6. Deterministic regional density contours.
   7. Sovereign reference geography with coastal lines.
   ═══════════════════════════════════════════════════════════════ */

export interface LineageLayerProps {
  id?: string;
  selectedPlotId: string;
  channels: VisualChannelProfile;
  opacity?: number;
}

export class LineageLayer extends CompositeLayer<LineageLayerProps> {
  static layerName = "LineageLayer";

  renderLayers() {
    const { selectedPlotId, channels, opacity = 1 } = this.props;
    const [plotId, farmId, portfolioId, regionId, countryId] = selectPlotLineage(selectedPlotId);

    const prepPlot = selectPreparedEntity(plotId);
    const prepFarm = selectPreparedEntity(farmId);
    const prepPortfolio = selectPreparedEntity(portfolioId);
    const prepRegion = selectPreparedEntity(regionId);

    if (!prepPlot) return [];

    const layers: any[] = [];
    const green: [number, number, number] = [74, 222, 128]; // #4ade80 AgriWise green
    const microMotion = channels.microMotion;

    // ── 1. Feature-by-Feature Member Parcels (FARM-04) ─────────
    const farmPlots = ILLUSTRATIVE_WORLD.plots.filter((p) => p.farmId === farmId);

    for (const plot of farmPlots) {
      const pState = microMotion?.parcelAcquisition?.[plot.id] || {
        id: plot.id,
        outlineProgress: plot.id === plotId ? 1.0 : 0.0,
        membershipMix: plot.id === plotId ? 1.0 : 0.0,
        acquisitionFlash: 0.0,
        emphasis: plot.id === plotId ? 1.0 : 0.0,
      };

      if (pState.outlineProgress <= 0.01) continue;

      const prep = selectPreparedEntity(plot.id);
      if (!prep) continue;

      const isProtagonist = plot.id === plotId;

      // A. Progressive Perimeter Draw Stroke
      if (pState.outlineProgress < 0.99) {
        const slicedStroke = slicePathByProgress(prep, pState.outlineProgress);
        if (slicedStroke.length > 1) {
          layers.push(
            new PathLayer({
              id: `${this.id}-plot-stroke-${plot.id}`,
              data: [{ path: slicedStroke }],
              getPath: (d: any) => d.path,
              getColor: [...green, Math.round(255 * opacity)],
              getWidth: isProtagonist ? 3.0 : 2.2,
              widthMinPixels: 2.0,
            })
          );
        }
      }

      // B. Settled / Acquiring Parcel Polygon (Crisp outline + 3-5% fill)
      if (pState.outlineProgress > 0.05) {
        const strokeAlpha = Math.min(1.0, pState.outlineProgress * 1.5);
        const fillAlpha = pState.membershipMix * (isProtagonist ? 24 : 14);
        const flashAlpha = pState.acquisitionFlash * 40;
        const lineWidth = isProtagonist ? 2.8 : 2.0;

        layers.push(
          new GeoJsonLayer({
            id: `${this.id}-plot-poly-${plot.id}`,
            data: {
              type: "Feature",
              geometry: { type: "Polygon", coordinates: [prep.hullCoordinates] },
            } as any,
            filled: fillAlpha > 0 || flashAlpha > 0,
            stroked: true,
            getFillColor: [...green, Math.round((fillAlpha + flashAlpha) * opacity)],
            getLineColor: [...green, Math.round((strokeAlpha * 190 + pState.acquisitionFlash * 65) * opacity)],
            getLineWidth: lineWidth,
            lineWidthMinPixels: 1.8,
          })
        );
      }
    }

    // ── 2. Protagonist Corner Ticks Micro-Animation ─────────────
    if (prepPlot && microMotion?.cornerTicks?.length) {
      const tickFeatures = microMotion.cornerTicks.map((tick) => {
        const pt = prepPlot.hullCoordinates[tick.vertexIndex] || prepPlot.hullCoordinates[0];
        return {
          id: `tick-${tick.vertexIndex}`,
          position: pt,
          progress: tick.progress,
          alpha: tick.opacity,
        };
      });

      layers.push(
        new ScatterplotLayer({
          id: `${this.id}-plot-corner-ticks`,
          data: tickFeatures,
          getPosition: (d: any) => d.position,
          getRadius: 4,
          radiusMinPixels: 3,
          radiusMaxPixels: 5,
          getFillColor: (d: any) => [...green, Math.round(240 * d.alpha * opacity)],
          getLineColor: (d: any) => [255, 255, 255, Math.round(200 * d.alpha * opacity)],
          lineWidthMinPixels: 1.0,
          stroked: true,
        })
      );
    }

    // ── 3. Soft Farm Grouping Envelope (Subtle 1.2px Outer Boundary) ────
    if (prepFarm && microMotion?.farmEnvelope?.drawProgress > 0.02) {
      const env = microMotion.farmEnvelope;

      if (env.drawProgress < 0.99) {
        const sliced = slicePathByProgress(prepFarm, env.drawProgress);
        if (sliced.length > 1) {
          layers.push(
            new PathLayer({
              id: `${this.id}-farm-envelope-stroke`,
              data: [{ path: sliced }],
              getPath: (d: any) => d.path,
              getColor: [...green, Math.round(180 * opacity)],
              getWidth: 1.4,
              widthMinPixels: 1.0,
            })
          );
        }
      }

      if (env.opacity > 0.02) {
        layers.push(
          new GeoJsonLayer({
            id: `${this.id}-farm-envelope-settled`,
            data: {
              type: "Feature",
              geometry: { type: "Polygon", coordinates: [prepFarm.hullCoordinates] },
            } as any,
            filled: true,
            stroked: true,
            getFillColor: [...green, Math.round((env.opacity * 10 + env.flash * 25) * opacity)],
            getLineColor: [...green, Math.round((env.opacity * 160 + env.flash * 80) * opacity)],
            getLineWidth: 1.2,
            lineWidthMinPixels: 1.0,
          })
        );
      }
    }

    // ── 4. Distributed Organization Topology (Network Paths & Nodes) ─
    if (prepPortfolio && channels.organizationLinks > 0.02) {
      const sisterFarms = ILLUSTRATIVE_WORLD.farms.filter((f) => f.portfolioId === portfolioId);
      const linkPaths = sisterFarms.map((f) => {
        const prep = selectPreparedEntity(f.id);
        return [prepFarm?.centroid || prepPlot.centroid, prep?.centroid || prepPlot.centroid];
      });

      layers.push(
        new PathLayer({
          id: `${this.id}-org-network-paths`,
          data: linkPaths.map((path) => ({ path })),
          getPath: (d: any) => d.path,
          getColor: [...green, Math.round(channels.organizationLinks * 180 * opacity)],
          getWidth: 1.6,
          widthMinPixels: 1.2,
        })
      );

      // Distributed farm topology nodes (clean small markers, not giant dots)
      if (channels.organizationTopologyNodes > 0.02) {
        const farmNodes = sisterFarms.map((f) => ({
          position: selectPreparedEntity(f.id)?.centroid || prepPlot.centroid,
          id: f.id,
        }));

        layers.push(
          new ScatterplotLayer({
            id: `${this.id}-org-farm-nodes`,
            data: farmNodes,
            getPosition: (d: any) => d.position,
            getRadius: 50,
            radiusMinPixels: 4,
            radiusMaxPixels: 8,
            getFillColor: [...green, Math.round(channels.organizationTopologyNodes * 220 * opacity)],
            getLineColor: [255, 255, 255, Math.round(channels.organizationTopologyNodes * 200 * opacity)],
            lineWidthMinPixels: 1.2,
          })
        );
      }
    }

    // ── 5. Deterministic Regional Density Contours ─────────────
    if (channels.regionalAggregationField > 0.02) {
      const revealProgress = channels.contourRevealProgress;
      const features = (regionalDensityGeojson.features as any[]).filter(
        (f) => f.properties.level <= Math.ceil(revealProgress * 5)
      );

      layers.push(
        new GeoJsonLayer({
          id: `${this.id}-regional-density-contours`,
          data: { type: "FeatureCollection", features } as any,
          filled: true,
          stroked: true,
          getFillColor: (d: any) => [
            d.properties?.color?.[0] ?? green[0],
            d.properties?.color?.[1] ?? green[1],
            d.properties?.color?.[2] ?? green[2],
            Math.round(8 * channels.regionalAggregationField * opacity),
          ] as [number, number, number, number],
          getLineColor: (d: any) => [
            d.properties?.color?.[0] ?? green[0],
            d.properties?.color?.[1] ?? green[1],
            d.properties?.color?.[2] ?? green[2],
            Math.round(140 * channels.regionalAggregationField * opacity),
          ] as [number, number, number, number],
          getLineWidth: 1.5,
          lineWidthMinPixels: 1.0,
        })
      );
    }

    // Selected Mitidja Region vector boundary
    if (prepRegion && channels.selectedRegion > 0.02) {
      layers.push(
        new GeoJsonLayer({
          id: `${this.id}-region-mitidja`,
          data: {
            type: "Feature",
            geometry: { type: "Polygon", coordinates: [prepRegion.hullCoordinates] },
          } as any,
          filled: true,
          stroked: true,
          getFillColor: [...green, Math.round(channels.selectedRegion * 16 * opacity)],
          getLineColor: [...green, Math.round(channels.selectedRegion * 200 * opacity)],
          getLineWidth: 2.2,
          lineWidthMinPixels: 1.5,
        })
      );
    }

    // ── 6. Sovereign Algeria Reference Geography ────────────────
    if (channels.countryBoundary > 0.02) {
      layers.push(
        new GeoJsonLayer({
          id: `${this.id}-country-algeria`,
          data: {
            type: "Feature",
            geometry: { type: "Polygon", coordinates: [ILLUSTRATIVE_WORLD.country.coordinates] },
          } as any,
          filled: true,
          stroked: true,
          getFillColor: [...green, Math.round(channels.countryBoundary * 12 * opacity)],
          getLineColor: [...green, Math.round(channels.countryBoundary * 220 * opacity)],
          getLineWidth: 2.5,
          lineWidthMinPixels: 1.5,
        })
      );
    }

    return layers;
  }
}
