/**
 * Irrigation Runtime — TypeScript Type Definitions v1.0.0
 *
 * Client-side type mirrors for the Python backend irrigation schemas.
 * Ensures type-safe API communication between frontend and backend.
 */

// ============================================================================
// Enums
// ============================================================================

export type IrrigationSystemType =
  | 'DRIP'
  | 'SPRINKLER'
  | 'CENTER_PIVOT'
  | 'LINEAR_MOVE'
  | 'FLOOD'
  | 'MICRO_SPRAY'
  | 'SUBSURFACE_DRIP';

export type CommandType =
  | 'START_ZONE'
  | 'STOP_ZONE'
  | 'SET_FLOW_RATE'
  | 'SET_PRESSURE'
  | 'EMERGENCY_STOP'
  | 'PULSE_IRRIGATE'
  | 'FERTIGATION_START'
  | 'FERTIGATION_STOP'
  | 'SET_PIVOT_SPEED'
  | 'SET_PIVOT_ANGLE'
  | 'SYSTEM_FLUSH'
  | 'QUERY_STATUS';

export type CommandPriority = 'LOW' | 'NORMAL' | 'HIGH' | 'CRITICAL' | 'EMERGENCY';

export type EventStatus =
  | 'SCHEDULED'
  | 'APPROVED'
  | 'QUEUED'
  | 'DISPATCHING'
  | 'EXECUTING'
  | 'VALIDATING'
  | 'COMPLETED'
  | 'FAILED'
  | 'CANCELLED'
  | 'DEFERRED'
  | 'EMERGENCY_STOPPED';

export type ActuatorStatus =
  | 'ONLINE'
  | 'OFFLINE'
  | 'EXECUTING'
  | 'ERROR'
  | 'MAINTENANCE'
  | 'UNKNOWN';

export type AutomationMode = 'MANUAL' | 'SEMI_AUTO' | 'FULL_AUTO';

export type ValidationOutcome =
  | 'CONFIRMED'
  | 'UNDER_DELIVERY'
  | 'OVER_DELIVERY'
  | 'NO_RESPONSE'
  | 'SENSOR_OFFLINE'
  | 'PENDING';

export type VendorId =
  | 'GENERIC'
  | 'HUNTER'
  | 'RAIN_BIRD'
  | 'NETAFIM'
  | 'LINDSAY'
  | 'VALLEY'
  | 'TORO'
  | 'JAIN'
  | 'RIVULIS'
  | 'GALCON'
  | 'BACCARA'
  | 'BERMAD'
  | 'CUSTOM';

export type DriverProtocol =
  | 'MQTT'
  | 'MODBUS_RTU'
  | 'MODBUS_TCP'
  | 'LORAWAN'
  | 'HTTP_REST'
  | 'BLUETOOTH'
  | 'CELLULAR_AT';

// ============================================================================
// Core Interfaces
// ============================================================================

export interface IrrigationCommand {
  command_id: string;
  command_type: CommandType;
  device_id: string;
  zone_id: string;
  plot_id: string;
  volume_mm: number;
  duration_minutes: number;
  flow_rate_lpm: number;
  pressure_bar: number;
  priority: CommandPriority;
  scheduled_at: string;
  source_event_id: string;
  automation_mode: AutomationMode;
  approved_by: string;
}

export interface CommandResult {
  command_id: string;
  device_id: string;
  success: boolean;
  timestamp: string;
  actual_volume_l: number;
  actual_duration_minutes: number;
  actual_flow_rate_lpm: number;
  actual_pressure_bar: number;
  error_code: string;
  error_message: string;
  ack_latency_ms: number;
}

export interface IrrigationEvent {
  event_id: string;
  plot_id: string;
  zone_id: string;
  device_id: string;
  system_type: IrrigationSystemType;
  automation_mode: AutomationMode;
  status: EventStatus;
  target_volume_mm: number;
  target_duration_minutes: number;
  actual_volume_l: number;
  actual_duration_minutes: number;
  scheduled_start: string;
  scheduled_end: string;
  actual_start: string;
  actual_end: string;
  source_action_id: string;
  approved_by: string;
  validation_outcome: ValidationOutcome;
  pre_irrigation_vwc: number;
  post_irrigation_vwc: number;
  safety_violations: string[];
  emergency_stopped: boolean;
  emergency_stop_reason: string;
  water_consumed_mm: number;
  status_log: Array<{ from: string; to: string; timestamp: string; reason: string }>;
}

export interface ActuatorDevice {
  device_id: string;
  vendor: VendorId;
  model: string;
  protocol: DriverProtocol;
  farm_id: string;
  plot_id: string;
  zone_ids: string[];
  status: ActuatorStatus;
  last_seen: string;
  is_connected: boolean;
  capabilities: {
    system_type: IrrigationSystemType;
    max_flow_rate_lpm: number;
    valve_count: number;
    application_efficiency: number;
    supports_pulse: boolean;
    supports_variable_rate: boolean;
    fertigation_capable: boolean;
  };
  automation_mode: AutomationMode;
}

export interface IrrigationScheduleEntry {
  schedule_id: string;
  plot_id: string;
  zone_id: string;
  device_id: string;
  system_type: IrrigationSystemType;
  target_volume_mm: number;
  target_duration_minutes: number;
  scheduled_date: string;
  scheduled_time: string;
  optimal_time: string;
  source_action_id: string;
  urgency: 'LOW' | 'NORMAL' | 'HIGH' | 'CRITICAL';
  reason: string;
  automation_mode: AutomationMode;
  approval_status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'DEFERRED';
  weather_ok: boolean;
  quota_ok: boolean;
  phenology_ok: boolean;
  safety_ok: boolean;
  deferred_reason: string;
  rain_forecast_mm: number;
  approved_by?: string;
}

export interface WaterBudget {
  plot_id: string;
  season: string;
  season_quota_mm: number;
  season_consumed_mm: number;
  season_remaining_mm: number;
  daily_quota_mm: number;
  daily_consumed_mm: number;
  daily_remaining_mm: number;
  projected_season_total_mm: number;
  days_remaining_in_season: number;
  water_cost_per_m3: number;
  season_cost_eur: number;
}

export interface SafetyViolation {
  violation_id: string;
  interlock_type: string;
  device_id: string;
  zone_id: string;
  detected_at: string;
  resolved_at: string;
  sensor_value: number;
  threshold_value: number;
  action_taken: string;
  acknowledged_by: string;
}

export interface ValidationReport {
  report_id: string;
  event_id: string;
  plot_id: string;
  zone_id: string;
  outcome: ValidationOutcome;
  pre_irrigation_vwc: number;
  post_irrigation_vwc: number;
  expected_vwc_rise: number;
  actual_vwc_rise: number;
  delivery_efficiency_actual: number;
  calibration_adjustment: number;
  confidence: number;
  sensor_readings_count: number;
}

export interface FleetStatus {
  total_actuators: number;
  total_zones: number;
  status_summary: Record<ActuatorStatus, number>;
  devices: ActuatorDevice[];
}

export interface IrrigationDashboardData {
  fleet: FleetStatus;
  active_events: IrrigationEvent[];
  pending_schedule: IrrigationScheduleEntry[];
  water_budget: WaterBudget;
  safety_score: number;
  active_violations: SafetyViolation[];
  recent_validations: ValidationReport[];
}

// ============================================================================
// API Request/Response Types
// ============================================================================

export interface DispatchCommandRequest {
  device_id: string;
  zone_id: string;
  plot_id: string;
  command_type: CommandType;
  volume_mm?: number;
  duration_minutes?: number;
  flow_rate_lpm?: number;
  priority?: CommandPriority;
}

export interface ApproveScheduleRequest {
  schedule_id: string;
  approved_by: string;
}

export interface EmergencyStopRequest {
  scope: 'device' | 'zone' | 'farm';
  device_id?: string;
  zone_id?: string;
}

// ============================================================================
// UI Helper Types
// ============================================================================

export const SYSTEM_TYPE_LABELS: Record<IrrigationSystemType, string> = {
  DRIP: 'Drip',
  SPRINKLER: 'Sprinkler',
  CENTER_PIVOT: 'Center Pivot',
  LINEAR_MOVE: 'Linear Move',
  FLOOD: 'Flood',
  MICRO_SPRAY: 'Micro-Spray',
  SUBSURFACE_DRIP: 'Subsurface Drip',
};

export const STATUS_COLORS: Record<EventStatus, string> = {
  SCHEDULED: '#6B7280',
  APPROVED: '#3B82F6',
  QUEUED: '#8B5CF6',
  DISPATCHING: '#F59E0B',
  EXECUTING: '#10B981',
  VALIDATING: '#06B6D4',
  COMPLETED: '#22C55E',
  FAILED: '#EF4444',
  CANCELLED: '#9CA3AF',
  DEFERRED: '#F97316',
  EMERGENCY_STOPPED: '#DC2626',
};

export const ACTUATOR_STATUS_COLORS: Record<ActuatorStatus, string> = {
  ONLINE: '#22C55E',
  OFFLINE: '#6B7280',
  EXECUTING: '#3B82F6',
  ERROR: '#EF4444',
  MAINTENANCE: '#F59E0B',
  UNKNOWN: '#9CA3AF',
};

export const VENDOR_LOGOS: Record<VendorId, string> = {
  GENERIC: '⚙️',
  HUNTER: '🏹',
  RAIN_BIRD: '🐦',
  NETAFIM: '💧',
  LINDSAY: '🔄',
  VALLEY: '🏔️',
  TORO: '🐂',
  JAIN: '🌱',
  RIVULIS: '💦',
  GALCON: '🔧',
  BACCARA: '🎯',
  BERMAD: '🔩',
  CUSTOM: '🛠️',
};
