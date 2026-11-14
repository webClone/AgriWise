import { ScatterplotLayer } from "@deck.gl/layers";
import type { WorkspaceFeatureEnvelope } from "@/lib/agribrain/workspace-feature-envelope";

export interface WorkspaceEntityPinsLayerProps {
  entities: WorkspaceFeatureEnvelope[];
  selectedEntityId?: string | null;
  onEntityClick?: (entity: WorkspaceFeatureEnvelope) => void;
}

/**
 * DeckGL layer for rendering authoritative, registered agricultural entities
 * (e.g., ground-truth soil moisture probes, weather stations, cameras, drone missions, field observations)
 * directly on the field map.
 * 
 * Enforces Gate P05-G02: Strictly renders pins for entities with verified
 * registered coordinates. Unlocated devices/photos are excluded from this layer.
 */
export function getWorkspaceEntityPinsLayers(props: WorkspaceEntityPinsLayerProps) {
  const { entities, selectedEntityId, onEntityClick } = props;

  // Filter strictly for entities eligible for map pins
  const locatedEntities = entities.filter(
    (e) => e.display_eligibility?.eligible_for_map_pin && e.geometry?.coordinates
  );

  if (locatedEntities.length === 0) {
    return [];
  }

  // 1. Halo / Selection Ring Layer
  const haloLayer = new ScatterplotLayer<WorkspaceFeatureEnvelope>({
    id: "workspace-entity-pins-halo",
    data: locatedEntities,
    pickable: false,
    opacity: 0.9,
    stroked: true,
    filled: true,
    radiusScale: 1,
    radiusMinPixels: 9,
    radiusMaxPixels: 24,
    lineWidthMinPixels: 2,
    getPosition: (d) => d.geometry!.coordinates as [number, number],
    getRadius: (d) => {
      const isSelected = selectedEntityId === d.entity_id || selectedEntityId === d.envelope_id;
      return isSelected ? 13 : 8;
    },
    getFillColor: (d) => {
      const isSelected = selectedEntityId === d.entity_id || selectedEntityId === d.envelope_id;
      if (isSelected) return [34, 211, 238, 70]; // Cyan glow
      if (d.entity_kind === "CAMERA") return [168, 85, 247, 45]; // Violet glow
      if (d.entity_kind === "DRONE_MISSION") return [249, 115, 22, 45]; // Orange glow
      if (d.entity_kind === "FIELD_OBSERVATION" || d.entity_kind === "FIELD_EVENT") return [244, 63, 94, 45]; // Rose glow
      return [15, 23, 42, 140];
    },
    getLineColor: (d) => {
      const isSelected = selectedEntityId === d.entity_id || selectedEntityId === d.envelope_id;
      if (isSelected) return [34, 211, 238, 255];
      if (d.entity_kind === "CAMERA") return [168, 85, 247, 200];
      if (d.entity_kind === "DRONE_MISSION") return [249, 115, 22, 200];
      if (d.entity_kind === "FIELD_OBSERVATION" || d.entity_kind === "FIELD_EVENT") return [244, 63, 94, 200];
      return [255, 255, 255, 120];
    },
    updateTriggers: {
      getRadius: [selectedEntityId],
      getFillColor: [selectedEntityId],
      getLineColor: [selectedEntityId],
    },
  });

  // 2. Core Interactive Entity Pin Layer
  const coreLayer = new ScatterplotLayer<WorkspaceFeatureEnvelope>({
    id: "workspace-entity-pins-core",
    data: locatedEntities,
    pickable: true,
    opacity: 1.0,
    stroked: true,
    filled: true,
    radiusScale: 1,
    radiusMinPixels: 5,
    radiusMaxPixels: 13,
    lineWidthMinPixels: 1.5,
    getPosition: (d) => d.geometry!.coordinates as [number, number],
    getRadius: (d) => {
      const isSelected = selectedEntityId === d.entity_id || selectedEntityId === d.envelope_id;
      return isSelected ? 6.5 : 5;
    },
    getFillColor: (d) => {
      const isSelected = selectedEntityId === d.entity_id || selectedEntityId === d.envelope_id;
      if (isSelected) {
        return [34, 211, 238, 255]; // Bright cyan when selected
      }

      // Family 1: CAMERA (Optical Traps, Fixed Field Cameras)
      if (d.entity_kind === "CAMERA") {
        return [168, 85, 247, 255]; // Violet / Aperture Purple (#a855f7)
      }

      // Family 2: DRONE_MISSION (Waypoints, Flight Corridors)
      if (d.entity_kind === "DRONE_MISSION") {
        return [249, 115, 22, 255]; // Aviation Orange (#f97316)
      }

      // Family 3: FIELD_OBSERVATION / FIELD_EVENT (Scouting, Symptoms, Ground Samples)
      if (d.entity_kind === "FIELD_OBSERVATION" || d.entity_kind === "FIELD_EVENT") {
        return [244, 63, 94, 255]; // Observation Rose (#f43f5e)
      }

      // Family 4: SENSOR (IoT Telemetry, Soil Probes, Weather Stations)
      const isOnline = (d.properties as any)?.isOnline ?? true;
      const isFixture = (d.properties as any)?.is_benchmark_fixture ?? false;
      if (isFixture) {
        return [234, 179, 8, 255]; // Amber for synthetic benchmark fixtures
      }
      if (!isOnline) {
        return [148, 163, 184, 220]; // Muted slate if offline
      }

      const type = String((d.properties as any)?.type || "").toUpperCase();
      if (type.includes("MOISTURE")) {
        return [16, 185, 129, 255]; // Vibrant Emerald
      }
      if (type.includes("WEATHER")) {
        return [56, 189, 248, 255]; // Sky Blue
      }
      if (type.includes("TEMP")) {
        return [245, 158, 11, 255]; // Amber
      }
      if (type.includes("EC")) {
        return [167, 139, 250, 255]; // Purple
      }
      return [34, 197, 94, 255]; // General Green
    },
    getLineColor: () => [255, 255, 255, 240],
    onClick: (info) => {
      if (info.object && onEntityClick) {
        onEntityClick(info.object);
      }
    },
    updateTriggers: {
      getFillColor: [selectedEntityId],
      getRadius: [selectedEntityId],
    },
  });

  return [haloLayer, coreLayer];
}
