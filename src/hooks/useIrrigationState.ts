'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import type {
  IrrigationDashboardData,
  IrrigationEvent,
  IrrigationScheduleEntry,
  ActuatorDevice,
  WaterBudget,
  SafetyViolation,
  ValidationReport,
  FleetStatus,
  CommandResult,
  DispatchCommandRequest,
  ActuatorStatus,
  EventStatus,
  AutomationMode,
} from '@/lib/irrigation/types';

// ============================================================================
// Mock Data Generator (for development — replace with real API calls)
// ============================================================================

function generateMockFleet(): FleetStatus {
  const devices: ActuatorDevice[] = [
    {
      device_id: 'ACT-DRP-001',
      vendor: 'NETAFIM',
      model: 'NetBeat-A (Simulated)',
      protocol: 'HTTP_REST',
      farm_id: 'farm-1',
      plot_id: 'plot-1',
      zone_ids: ['zone-a', 'zone-b'],
      status: 'OFFLINE' as ActuatorStatus,
      last_seen: new Date().toISOString(),
      is_connected: false,
      capabilities: {
        system_type: 'DRIP',
        max_flow_rate_lpm: 1000,
        valve_count: 48,
        application_efficiency: 0.95,
        supports_pulse: true,
        supports_variable_rate: true,
        fertigation_capable: true,
      },
      automation_mode: 'SEMI_AUTO' as AutomationMode,
    },
    {
      device_id: 'ACT-PIV-001',
      vendor: 'LINDSAY',
      model: 'Zimmatic-9500 (Simulated)',
      protocol: 'HTTP_REST',
      farm_id: 'farm-1',
      plot_id: 'plot-2',
      zone_ids: ['zone-c'],
      status: 'OFFLINE' as ActuatorStatus,
      last_seen: new Date().toISOString(),
      is_connected: false,
      capabilities: {
        system_type: 'CENTER_PIVOT',
        max_flow_rate_lpm: 5000,
        valve_count: 1,
        application_efficiency: 0.85,
        supports_pulse: false,
        supports_variable_rate: true,
        fertigation_capable: false,
      },
      automation_mode: 'FULL_AUTO' as AutomationMode,
    },
    {
      device_id: 'ACT-SPR-001',
      vendor: 'HUNTER',
      model: 'Pro-HC (Simulated)',
      protocol: 'MQTT',
      farm_id: 'farm-1',
      plot_id: 'plot-3',
      zone_ids: ['zone-d', 'zone-e', 'zone-f'],
      status: 'OFFLINE' as ActuatorStatus,
      last_seen: new Date().toISOString(),
      is_connected: false,
      capabilities: {
        system_type: 'SPRINKLER',
        max_flow_rate_lpm: 500,
        valve_count: 24,
        application_efficiency: 0.82,
        supports_pulse: true,
        supports_variable_rate: false,
        fertigation_capable: false,
      },
      automation_mode: 'MANUAL' as AutomationMode,
    },
    {
      device_id: 'ACT-VLV-001',
      vendor: 'GALCON',
      model: 'GSI-AC24 (Simulated)',
      protocol: 'MQTT',
      farm_id: 'farm-1',
      plot_id: 'plot-1',
      zone_ids: ['zone-g'],
      status: 'OFFLINE' as ActuatorStatus,
      last_seen: new Date(Date.now() - 3600000).toISOString(),
      is_connected: false,
      capabilities: {
        system_type: 'DRIP',
        max_flow_rate_lpm: 300,
        valve_count: 24,
        application_efficiency: 0.93,
        supports_pulse: true,
        supports_variable_rate: false,
        fertigation_capable: true,
      },
      automation_mode: 'SEMI_AUTO' as AutomationMode,
    },
  ];

  return {
    total_actuators: devices.length,
    total_zones: 7,
    status_summary: {
      ONLINE: 0,
      OFFLINE: devices.length,
      EXECUTING: 0,
      ERROR: 0,
      MAINTENANCE: 0,
      UNKNOWN: 0,
    } as Record<ActuatorStatus, number>,
    devices,
  };
}

function generateMockEvents(): IrrigationEvent[] {
  // In observation-only mode without connected actuator hardware, there are
  // NO active or executing physical irrigation events.
  return [];
}

function generateMockSchedule(): IrrigationScheduleEntry[] {
  return [
    {
      schedule_id: 'SCH-001',
      plot_id: 'plot-1',
      zone_id: 'zone-a',
      device_id: 'ACT-DRP-001',
      system_type: 'DRIP',
      target_volume_mm: 15,
      target_duration_minutes: 225,
      scheduled_date: new Date(Date.now() + 86400000).toISOString().split('T')[0],
      scheduled_time: '05:00',
      optimal_time: '05:00',
      source_action_id: 'ACT-L8-002',
      urgency: 'HIGH',
      reason: 'Soil moisture at 22% VWC — below MAD threshold for flowering wheat',
      automation_mode: 'SEMI_AUTO',
      approval_status: 'PENDING',
      weather_ok: true,
      quota_ok: true,
      phenology_ok: true,
      safety_ok: true,
      deferred_reason: '',
      rain_forecast_mm: 2,
    },
    {
      schedule_id: 'SCH-002',
      plot_id: 'plot-3',
      zone_id: 'zone-d',
      device_id: 'ACT-SPR-001',
      system_type: 'SPRINKLER',
      target_volume_mm: 20,
      target_duration_minutes: 100,
      scheduled_date: new Date(Date.now() + 172800000).toISOString().split('T')[0],
      scheduled_time: '06:00',
      optimal_time: '06:00',
      source_action_id: 'ACT-L8-003',
      urgency: 'NORMAL',
      reason: 'Scheduled maintenance irrigation for vegetative stage citrus',
      automation_mode: 'SEMI_AUTO',
      approval_status: 'APPROVED',
      weather_ok: true,
      quota_ok: true,
      phenology_ok: true,
      safety_ok: true,
      deferred_reason: '',
      rain_forecast_mm: 0,
    },
    {
      schedule_id: 'SCH-003',
      plot_id: 'plot-1',
      zone_id: 'zone-b',
      device_id: 'ACT-DRP-001',
      system_type: 'DRIP',
      target_volume_mm: 10,
      target_duration_minutes: 150,
      scheduled_date: new Date(Date.now() + 259200000).toISOString().split('T')[0],
      scheduled_time: '04:30',
      optimal_time: '04:30',
      source_action_id: 'ACT-L8-004',
      urgency: 'LOW',
      reason: 'Precautionary irrigation ahead of heat wave',
      automation_mode: 'SEMI_AUTO',
      approval_status: 'DEFERRED',
      weather_ok: false,
      quota_ok: true,
      phenology_ok: true,
      safety_ok: true,
      deferred_reason: 'Rain forecast: 15mm in next 24h',
      rain_forecast_mm: 15,
    },
  ];
}

function generateMockBudget(): WaterBudget {
  return {
    plot_id: 'farm-1',
    season: '2026-SPRING',
    season_quota_mm: 800,
    season_consumed_mm: 0,
    season_remaining_mm: 800,
    daily_quota_mm: 40,
    daily_consumed_mm: 0,
    daily_remaining_mm: 40,
    projected_season_total_mm: 0,
    days_remaining_in_season: 85,
    water_cost_per_m3: 0.45,
    season_cost_eur: 0,
  };
}

// ============================================================================
// Hook
// ============================================================================

interface UseIrrigationStateOptions {
  farmId?: string;
  pollIntervalMs?: number;
  enableWebSocket?: boolean;
}

interface UseIrrigationStateReturn {
  // Data
  fleet: FleetStatus | null;
  activeEvents: IrrigationEvent[];
  pendingSchedule: IrrigationScheduleEntry[];
  waterBudget: WaterBudget | null;
  safetyScore: number;
  activeViolations: SafetyViolation[];
  recentValidations: ValidationReport[];

  // Loading / Error
  isLoading: boolean;
  error: string | null;

  // Observability & Simulation Scope
  isSimulationMode: boolean;
  isPhysicalHardwareConnected: boolean;
  actuatorLinkStatus: 'DISCONNECTED' | 'CONNECTED';

  // Actions
  dispatchCommand: (req: DispatchCommandRequest) => Promise<CommandResult | null>;
  approveSchedule: (scheduleId: string) => Promise<boolean>;
  rejectSchedule: (scheduleId: string) => Promise<boolean>;
  emergencyStopAll: () => Promise<boolean>;
  emergencyStopDevice: (deviceId: string) => Promise<boolean>;
  cancelEvent: (eventId: string) => Promise<boolean>;
  setAutomationMode: (deviceId: string, mode: AutomationMode) => void;
  refresh: () => void;
}

export function useIrrigationState(
  options: UseIrrigationStateOptions = {}
): UseIrrigationStateReturn {
  const { farmId = 'farm-1', pollIntervalMs = 10000 } = options;

  const [fleet, setFleet] = useState<FleetStatus | null>(null);
  const [activeEvents, setActiveEvents] = useState<IrrigationEvent[]>([]);
  const [pendingSchedule, setPendingSchedule] = useState<IrrigationScheduleEntry[]>([]);
  const [waterBudget, setWaterBudget] = useState<WaterBudget | null>(null);
  const [safetyScore, setSafetyScore] = useState(1.0);
  const [activeViolations, setActiveViolations] = useState<SafetyViolation[]>([]);
  const [recentValidations, setRecentValidations] = useState<ValidationReport[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  // ─── Data Fetching ───────────────────────────────────────────────
  const fetchData = useCallback(async () => {
    try {
      // In production, replace with real API calls:
      // const res = await fetch(`/api/irrigation/status?farm_id=${farmId}`);
      // const data: IrrigationDashboardData = await res.json();

      // Development: use mock data
      setFleet(generateMockFleet());
      setActiveEvents(generateMockEvents());
      setPendingSchedule(generateMockSchedule());
      setWaterBudget(generateMockBudget());
      setSafetyScore(0.95);
      setActiveViolations([]);
      setRecentValidations([]);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch irrigation data');
    } finally {
      setIsLoading(false);
    }
  }, [farmId]);

  // ─── Polling ─────────────────────────────────────────────────────
  useEffect(() => {
    fetchData();
    intervalRef.current = setInterval(fetchData, pollIntervalMs);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetchData, pollIntervalMs]);

  // ─── Actions ─────────────────────────────────────────────────────
  const dispatchCommand = useCallback(async (req: DispatchCommandRequest): Promise<CommandResult | null> => {
    try {
      console.warn('[Irrigation] Physical actuator hardware not connected. Simulated dispatch rejected fail-closed:', req);
      return {
        command_id: `SIM-${Date.now()}`,
        device_id: req.device_id,
        success: false,
        timestamp: new Date().toISOString(),
        actual_volume_l: 0,
        actual_duration_minutes: 0,
        actual_flow_rate_lpm: 0,
        actual_pressure_bar: 0,
        error_code: 'SIMULATION_NOT_CONNECTED',
        error_message: 'Physical actuator hardware is not connected. Simulation mode cannot execute real physical irrigation commands.',
        ack_latency_ms: 0,
      };
    } catch {
      return null;
    }
  }, []);

  const approveSchedule = useCallback(async (scheduleId: string): Promise<boolean> => {
    setPendingSchedule(prev =>
      prev.map(s => s.schedule_id === scheduleId
        ? { ...s, approval_status: 'APPROVED' as const, approved_by: 'farmer' }
        : s
      )
    );
    return true;
  }, []);

  const rejectSchedule = useCallback(async (scheduleId: string): Promise<boolean> => {
    setPendingSchedule(prev =>
      prev.map(s => s.schedule_id === scheduleId
        ? { ...s, approval_status: 'REJECTED' as const }
        : s
      )
    );
    return true;
  }, []);

  const emergencyStopAll = useCallback(async (): Promise<boolean> => {
    console.warn('[Irrigation] 🚨 EMERGENCY STOP CALLED (SIMULATION / NOT CONNECTED)');
    setActiveEvents(prev =>
      prev.map(e => ({
        ...e,
        status: 'EMERGENCY_STOPPED' as EventStatus,
        emergency_stopped: true,
        emergency_stop_reason: 'Simulated local emergency stop (hardware not connected)',
      }))
    );
    // Return false: Physical actuator acknowledgment was not obtained
    return false;
  }, []);

  const emergencyStopDevice = useCallback(async (deviceId: string): Promise<boolean> => {
    console.warn('[Irrigation] 🚨 EMERGENCY STOP device (SIMULATION / NOT CONNECTED):', deviceId);
    return false;
  }, []);

  const cancelEvent = useCallback(async (eventId: string): Promise<boolean> => {
    console.warn('[Irrigation] Physical actuator hardware not connected. Cancel command not acknowledged physically.');
    setActiveEvents(prev => prev.filter(e => e.event_id !== eventId));
    // Return false: Physical cancellation was not acknowledged by field hardware
    return false;
  }, []);

  const setAutomationMode = useCallback((deviceId: string, mode: AutomationMode) => {
    setFleet(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        devices: prev.devices.map(d =>
          d.device_id === deviceId ? { ...d, automation_mode: mode } : d
        ),
      };
    });
  }, []);

  return {
    fleet,
    activeEvents,
    pendingSchedule,
    waterBudget,
    safetyScore,
    activeViolations,
    recentValidations,
    isLoading,
    error,
    isSimulationMode: true,
    isPhysicalHardwareConnected: false,
    actuatorLinkStatus: 'DISCONNECTED' as const,
    dispatchCommand,
    approveSchedule,
    rejectSchedule,
    emergencyStopAll,
    emergencyStopDevice,
    cancelEvent,
    setAutomationMode,
    refresh: fetchData,
  };
}
