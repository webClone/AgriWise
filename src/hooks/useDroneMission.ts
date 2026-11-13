"use client";

/**
 * useDroneMission — React hook for drone mission orchestration.
 *
 * Provides:
 *   - suggestions: anomaly-based mission suggestions for the current plot
 *   - activeMission: state of the currently dispatched mission (polled)
 *   - flightPlan: the latest generated flight plan
 *   - planMission / dispatchMission / controlMission actions
 */

import { useState, useCallback, useEffect, useRef } from "react";

const API_BASE = "/api/agribrain/drone";

export interface MissionSuggestion {
  intent_id: string;
  mission_type: string;
  flight_mode: string;
  urgency_score: number;
  reason: string;
  suppressed: boolean;
  suppression_reason: string;
  target_gsd_cm: number;
  polygon_geojson: any;
  plot_id: string;
}

export interface FlightPlan {
  plan_id: string;
  intent_id: string;
  drone_profile: string;
  pattern: string;
  waypoint_count: number;
  waypoints: { lat: number; lon: number; alt_m: number; action: string }[];
  estimated_flight_time_min: number;
  estimated_image_count: number;
  achieved_gsd_cm: number;
  flight_altitude_m: number;
  is_feasible: boolean;
  infeasibility_reason: string | null;
}

export interface MissionState {
  execution_id: string;
  mission_id: string;
  state: string;
  is_terminal: boolean;
  telemetry: {
    battery_pct?: number;
    altitude_m?: number;
    groundspeed_m_s?: number;
    capture_count?: number;
    mission_progress_pct?: number;
    current_waypoint?: number;
    total_waypoints?: number;
    lat?: number;
    lng?: number;
  };
}

export interface MissionHistoryItem {
  execution_id: string;
  mission_id: string;
  plot_id: string;
  mission_type: string;
  flight_mode: string;
  status: string;
  success: boolean;
  timestamp: string;
  duration_s?: number;
  coverage_pct?: number;
  actual_captures?: number;
  battery_used_pct?: number;
}

export interface DroneStatus {
  connected: boolean;
  battery_pct: number;
  gps_fix: boolean;
  gps_satellites: number;
  gps_hdop: number;
  storage_mb: number;
  armed: boolean;
  link_quality_pct: number;
}

export interface WeatherInfo {
  wind_speed_m_s: number;
  wind_direction_deg: number;
  temperature_c: number;
  humidity_pct: number;
  visibility_km: number;
  precipitation: boolean;
}

export interface PreflightCheck {
  id: string;
  label: string;
  status: "pass" | "warn" | "fail" | "pending";
  detail: string;
}

export type DroneTab = "planner" | "flightplan" | "telemetry" | "history";

type DronePhase = "idle" | "planning" | "planned" | "dispatching" | "active" | "completed";

function buildPreflightChecks(drone: DroneStatus, weather: WeatherInfo, hasPolygon: boolean): PreflightCheck[] {
  return [
    { id: "gps", label: "GPS Fix", status: drone.gps_fix && drone.gps_satellites >= 6 ? "pass" : drone.gps_fix ? "warn" : "fail", detail: drone.gps_fix ? `${drone.gps_satellites} sats, HDOP ${drone.gps_hdop.toFixed(1)}` : "No GPS fix" },
    { id: "battery", label: "Battery", status: drone.battery_pct > 30 ? "pass" : drone.battery_pct > 20 ? "warn" : "fail", detail: `${drone.battery_pct.toFixed(0)}% charged` },
    { id: "wind", label: "Wind", status: weather.wind_speed_m_s < 8 ? "pass" : weather.wind_speed_m_s < 12 ? "warn" : "fail", detail: `${weather.wind_speed_m_s.toFixed(1)} m/s` },
    { id: "precip", label: "Precipitation", status: weather.precipitation ? "fail" : "pass", detail: weather.precipitation ? "Rain detected" : "Clear" },
    { id: "storage", label: "Storage", status: drone.storage_mb > 2000 ? "pass" : drone.storage_mb > 500 ? "warn" : "fail", detail: `${(drone.storage_mb / 1024).toFixed(1)} GB free` },
    { id: "link", label: "Data Link", status: drone.link_quality_pct > 60 ? "pass" : drone.link_quality_pct > 30 ? "warn" : "fail", detail: `${drone.link_quality_pct.toFixed(0)}% signal` },
    { id: "polygon", label: "Plot Polygon", status: hasPolygon ? "pass" : "fail", detail: hasPolygon ? "Boundary defined" : "No polygon" },
  ];
}

export function useDroneMission(plotId: string, polygonGeoJson?: any) {
  const [phase, setPhase] = useState<DronePhase>("idle");
  const [suggestions, setSuggestions] = useState<MissionSuggestion[]>([]);
  const [flightPlan, setFlightPlan] = useState<FlightPlan | null>(null);
  const [activeMission, setActiveMission] = useState<MissionState | null>(null);
  const [history, setHistory] = useState<MissionHistoryItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<DroneTab>("planner");
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Simulated drone status (explicitly flagged as NOT CONNECTED for safety)
  const [droneStatus] = useState<DroneStatus>({
    connected: false,
    battery_pct: 0,
    gps_fix: false,
    gps_satellites: 0,
    gps_hdop: 99.9,
    storage_mb: 0,
    armed: false,
    link_quality_pct: 0,
  });
  const [weather] = useState<WeatherInfo>({
    wind_speed_m_s: 3.2, wind_direction_deg: 225, temperature_c: 28,
    humidity_pct: 45, visibility_km: 12, precipitation: false,
  });
  const preflightChecks = buildPreflightChecks(droneStatus, weather, !!polygonGeoJson);

  // Fetch suggestions
  const fetchSuggestions = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/suggest/${plotId}`);
      if (res.ok) {
        const data = await res.json();
        setSuggestions(data.suggestions || []);
      }
    } catch {
      /* swallow — backend may not be running */
    }
  }, [plotId]);

  // Fetch history
  const fetchHistory = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/missions?plot_id=${plotId}&limit=10`);
      if (res.ok) {
        const data = await res.json();
        setHistory(data.missions || []);
      }
    } catch {
      /* swallow */
    }
  }, [plotId]);

  // Plan a mission
  const planMission = useCallback(async (opts?: {
    mission_type?: string;
    flight_mode?: string;
    target_gsd_cm?: number;
    overlap_pct?: number;
    target_zone_id?: string;
  }) => {
    if (!polygonGeoJson) {
      setError("No polygon available for this plot");
      return null;
    }
    setLoading(true);
    setError(null);
    setPhase("planning");

    try {
      const res = await fetch(`${API_BASE}/plan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          plot_id: plotId,
          mission_type: opts?.mission_type || "full_plot_map",
          flight_mode: opts?.flight_mode || "mapping_mode",
          polygon_geojson: polygonGeoJson,
          target_gsd_cm: opts?.target_gsd_cm || 2.0,
          required_overlap_pct: opts?.overlap_pct || 70.0,
          target_zone_id: opts?.target_zone_id || null,
          trigger_source: "manual",
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to plan mission");
      }

      const plan: FlightPlan = await res.json();
      setFlightPlan(plan);
      setPhase("planned");
      return plan;
    } catch (e: any) {
      setError(e.message);
      setPhase("idle");
      return null;
    } finally {
      setLoading(false);
    }
  }, [plotId, polygonGeoJson]);

  // Dispatch a planned mission
  const dispatchMission = useCallback(async (planId?: string) => {
    if (!droneStatus.connected) {
      setError("Physical drone is not connected (Simulation / Disconnected). Physical dispatch disabled.");
      return null;
    }

    const pid = planId || flightPlan?.plan_id;
    if (!pid) {
      setError("No flight plan to dispatch");
      return null;
    }
    setLoading(true);
    setError(null);
    setPhase("dispatching");

    try {
      const res = await fetch(`${API_BASE}/dispatch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          plot_id: plotId,
          plan_id: pid,
          driver_type: "mock",
          vehicle_id: "sim_drone_01",
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to dispatch mission");
      }

      const result = await res.json();
      setActiveMission({
        execution_id: result.execution_id,
        mission_id: result.mission_id,
        state: result.state,
        is_terminal: ["completed", "aborted", "failed"].includes(result.state),
        telemetry: {},
      });

      if (result.success) {
        setPhase("completed");
      } else {
        setPhase("completed");
        setError(result.failure_reason || "Mission failed");
      }

      // Refresh history
      fetchHistory();
      return result;
    } catch (e: any) {
      setError(e.message);
      setPhase("idle");
      return null;
    } finally {
      setLoading(false);
    }
  }, [flightPlan, fetchHistory, plotId]);

  // Control an active mission
  const controlMission = useCallback(async (action: "pause" | "resume" | "abort" | "rtl") => {
    if (!activeMission?.execution_id) return false;

    try {
      const res = await fetch(
        `${API_BASE}/missions/${activeMission.execution_id}/control`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action, plot_id: plotId }),
        }
      );
      if (res.ok) {
        const data = await res.json();
        setActiveMission(prev => prev ? { ...prev, state: data.new_state } : null);
        return data.success;
      }
      return false;
    } catch {
      return false;
    }
  }, [activeMission, plotId]);

  // Cancel planning
  const cancelPlan = useCallback(() => {
    setFlightPlan(null);
    setPhase("idle");
    setError(null);
  }, []);

  // Reset state
  const reset = useCallback(() => {
    setPhase("idle");
    setFlightPlan(null);
    setActiveMission(null);
    setError(null);
  }, []);

  // Load initial data
  useEffect(() => {
    if (plotId) {
      fetchSuggestions();
      fetchHistory();
    }
  }, [plotId, fetchSuggestions, fetchHistory]);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  return {
    // State
    phase,
    suggestions,
    flightPlan,
    activeMission,
    history,
    error,
    loading,
    activeTab,
    setActiveTab,
    droneStatus,
    weather,
    preflightChecks,

    // Actions
    planMission,
    dispatchMission,
    controlMission,
    cancelPlan,
    reset,
    fetchSuggestions,
    fetchHistory,
  };
}
