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
      model: 'NetBeat-A',
      protocol: 'HTTP_REST',
      farm_id: 'farm-1',
      plot_id: 'plot-1',
      zone_ids: ['zone-a', 'zone-b'],
      status: 'ONLINE' as ActuatorStatus,
      last_seen: new Date().toISOString(),
      is_connected: true,
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
      model: 'Zimmatic-9500',
      protocol: 'HTTP_REST',
      farm_id: 'farm-1',
      plot_id: 'plot-2',
      zone_ids: ['zone-c'],
      status: 'EXECUTING' as ActuatorStatus,
      last_seen: new Date().toISOString(),
      is_connected: true,
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
      model: 'Pro-HC',
      protocol: 'MQTT',
      farm_id: 'farm-1',
      plot_id: 'plot-3',
      zone_ids: ['zone-d', 'zone-e', 'zone-f'],
      status: 'ONLINE' as ActuatorStatus,
      last_seen: new Date().toISOString(),
      is_connected: true,
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
      model: 'GSI-AC24',
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
      ONLINE: 2,
      OFFLINE: 1,
      EXECUTING: 1,
      ERROR: 0,
      MAINTENANCE: 0,
      UNKNOWN: 0,
    } as Record<ActuatorStatus, number>,
    devices,
  };
}

function generateMockEvents(): IrrigationEvent[] {
  return [
    {
      event_id: 'EVT-a1b2c3d4e5f6',
      plot_id: 'plot-2',
      zone_id: 'zone-c',
      device_id: 'ACT-PIV-001',
      system_type: 'CENTER_PIVOT',
      automation_mode: 'FULL_AUTO',
      status: 'EXECUTING' as EventStatus,
      target_volume_mm: 25,
      target_duration_minutes: 120,
      actual_volume_l: 12500,
      actual_duration_minutes: 65,
      scheduled_start: new Date(Date.now() - 3900000).toISOString(),
      scheduled_end: new Date(Date.now() + 3300000).toISOString(),
      actual_start: new Date(Date.now() - 3900000).toISOString(),
      actual_end: '',
      source_action_id: 'ACT-L8-001',
      approved_by: 'SYSTEM_AUTO',
      validation_outcome: 'PENDING',
      pre_irrigation_vwc: 0.18,
      post_irrigation_vwc: 0,
      safety_violations: [],
      emergency_stopped: false,
      emergency_stop_reason: '',
      water_consumed_mm: 13.5,
      status_log: [
        { from: 'SCHEDULED', to: 'QUEUED', timestamp: new Date(Date.now() - 4200000).toISOString(), reason: 'Created from schedule' },
        { from: 'QUEUED', to: 'DISPATCHING', timestamp: new Date(Date.now() - 4000000).toISOString(), reason: 'Starting dispatch' },
        { from: 'DISPATCHING', to: 'EXECUTING', timestamp: new Date(Date.now() - 3900000).toISOString(), reason: 'ACK received' },
      ],
    },
  ];
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
    season_consumed_mm: 340,
    season_remaining_mm: 460,
    daily_quota_mm: 40,
    daily_consumed_mm: 13.5,
    daily_remaining_mm: 26.5,
    projected_season_total_mm: 720,
    days_remaining_in_season: 85,
    water_cost_per_m3: 0.45,
    season_cost_eur: 1530,
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
      // const res = await fetch('/api/irrigation/command', {
      //   method: 'POST', body: JSON.stringify(req), headers: { 'Content-Type': 'application/json' }
      // });
      // return await res.json();
      console.log('[Irrigation] Dispatch command:', req);
      return {
        command_id: `CMD-${Date.now()}`,
        device_id: req.device_id,
        success: true,
        timestamp: new Date().toISOString(),
        actual_volume_l: 0,
        actual_duration_minutes: 0,
        actual_flow_rate_lpm: 0,
        actual_pressure_bar: 0,
        error_code: '',
        error_message: '',
        ack_latency_ms: 150,
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
    console.log('[Irrigation] 🚨 EMERGENCY STOP ALL');
    setActiveEvents(prev =>
      prev.map(e => ({ ...e, status: 'EMERGENCY_STOPPED' as EventStatus, emergency_stopped: true }))
    );
    return true;
  }, []);

  const emergencyStopDevice = useCallback(async (deviceId: string): Promise<boolean> => {
    console.log('[Irrigation] 🚨 EMERGENCY STOP device:', deviceId);
    return true;
  }, []);

  const cancelEvent = useCallback(async (eventId: string): Promise<boolean> => {
    setActiveEvents(prev =>
      prev.map(e => e.event_id === eventId
        ? { ...e, status: 'CANCELLED' as EventStatus }
        : e
      )
    );
    return true;
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
