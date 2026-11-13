'use client';

import React, { useState, useMemo } from 'react';
import { useIrrigationState } from '@/hooks/useIrrigationState';
import {
  SYSTEM_TYPE_LABELS,
  STATUS_COLORS,
  ACTUATOR_STATUS_COLORS,
  VENDOR_LOGOS,
} from '@/lib/irrigation/types';
import type {
  ActuatorDevice,
  IrrigationEvent,
  IrrigationScheduleEntry,
  AutomationMode,
  EventStatus,
} from '@/lib/irrigation/types';

/* ================================================================
   Sub-Components
   ================================================================ */

function SafetyBadge({ score }: { score: number }) {
  const color = score >= 0.8 ? '#22C55E' : score >= 0.5 ? '#F59E0B' : '#EF4444';
  const label = score >= 0.8 ? 'NOMINAL' : score >= 0.5 ? 'WARNING' : 'CRITICAL';
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      padding: '4px 12px', borderRadius: 20,
      background: `${color}18`, color, fontSize: 12, fontWeight: 700,
      border: `1px solid ${color}40`,
    }}>
      <span style={{ width: 8, height: 8, borderRadius: '50%', background: color }} />
      {label} — {Math.round(score * 100)}%
    </span>
  );
}

function StatCard({ label, value, sub, accent = '#3B82F6' }: {
  label: string; value: string | number; sub?: string; accent?: string;
}) {
  return (
    <div style={{
      background: 'rgba(255,255,255,0.04)', borderRadius: 16,
      padding: '20px 24px', border: '1px solid rgba(255,255,255,0.06)',
      flex: '1 1 180px', minWidth: 160,
    }}>
      <div style={{ fontSize: 12, color: '#94A3B8', marginBottom: 8, fontWeight: 500 }}>{label}</div>
      <div style={{ fontSize: 28, fontWeight: 700, color: accent, lineHeight: 1 }}>{value}</div>
      {sub && <div style={{ fontSize: 11, color: '#64748B', marginTop: 6 }}>{sub}</div>}
    </div>
  );
}

function DeviceRow({ device, onModeChange }: {
  device: ActuatorDevice;
  onModeChange: (id: string, mode: AutomationMode) => void;
}) {
  const statusColor = ACTUATOR_STATUS_COLORS[device.status] || '#6B7280';
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px',
      borderRadius: 12, background: 'rgba(255,255,255,0.02)',
      border: '1px solid rgba(255,255,255,0.05)', fontSize: 13,
    }}>
      <span style={{ fontSize: 20 }}>{VENDOR_LOGOS[device.vendor] || '⚙️'}</span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontWeight: 600, color: '#E2E8F0' }}>{device.model}</div>
        <div style={{ color: '#64748B', fontSize: 11 }}>
          {device.device_id} · {SYSTEM_TYPE_LABELS[device.capabilities.system_type]}
        </div>
      </div>
      <span style={{
        padding: '3px 10px', borderRadius: 12, fontSize: 11, fontWeight: 600,
        background: `${statusColor}18`, color: statusColor, border: `1px solid ${statusColor}30`,
      }}>
        {device.status}
      </span>
      <select
        value={device.automation_mode}
        onChange={e => onModeChange(device.device_id, e.target.value as AutomationMode)}
        style={{
          background: 'rgba(255,255,255,0.06)', color: '#CBD5E1', border: '1px solid rgba(255,255,255,0.1)',
          borderRadius: 8, padding: '4px 8px', fontSize: 11, cursor: 'pointer',
        }}
      >
        <option value="MANUAL">Manual</option>
        <option value="SEMI_AUTO">Semi-Auto</option>
        <option value="FULL_AUTO">Full Auto</option>
      </select>
    </div>
  );
}

function ScheduleRow({ entry, onApprove, onReject }: {
  entry: IrrigationScheduleEntry;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
}) {
  const urgencyColors: Record<string, string> = {
    CRITICAL: '#EF4444', HIGH: '#F59E0B', NORMAL: '#3B82F6', LOW: '#6B7280',
  };
  const uc = urgencyColors[entry.urgency] || '#6B7280';
  const statusBg: Record<string, string> = {
    PENDING: '#F59E0B', APPROVED: '#22C55E', REJECTED: '#EF4444', DEFERRED: '#F97316',
  };
  const sb = statusBg[entry.approval_status] || '#6B7280';

  return (
    <div style={{
      padding: '14px 16px', borderRadius: 12,
      background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
        <span style={{
          padding: '2px 8px', borderRadius: 8, fontSize: 10, fontWeight: 700,
          background: `${uc}20`, color: uc,
        }}>
          {entry.urgency}
        </span>
        <span style={{ color: '#E2E8F0', fontSize: 13, fontWeight: 600, flex: 1 }}>
          {SYSTEM_TYPE_LABELS[entry.system_type]} — {entry.target_volume_mm}mm
        </span>
        <span style={{
          padding: '2px 8px', borderRadius: 8, fontSize: 10, fontWeight: 600,
          background: `${sb}20`, color: sb,
        }}>
          {entry.approval_status}
        </span>
      </div>
      <div style={{ fontSize: 11, color: '#94A3B8', marginBottom: 6 }}>{entry.reason}</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, color: '#64748B' }}>
        <span>📅 {entry.scheduled_date}</span>
        <span>⏰ {entry.optimal_time}</span>
        <span>⏱️ {entry.target_duration_minutes}min</span>
        {entry.rain_forecast_mm > 0 && <span>🌧️ {entry.rain_forecast_mm}mm</span>}
        {entry.deferred_reason && <span style={{ color: '#F97316' }}>⚠️ {entry.deferred_reason}</span>}
      </div>
      {entry.approval_status === 'PENDING' && (
        <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
          <button onClick={() => onApprove(entry.schedule_id)} style={{
            padding: '6px 16px', borderRadius: 8, border: 'none', cursor: 'pointer',
            background: '#22C55E', color: '#fff', fontSize: 12, fontWeight: 600,
          }}>✓ Approve</button>
          <button onClick={() => onReject(entry.schedule_id)} style={{
            padding: '6px 16px', borderRadius: 8, border: '1px solid rgba(255,255,255,0.1)',
            cursor: 'pointer', background: 'transparent', color: '#94A3B8', fontSize: 12,
          }}>✕ Reject</button>
        </div>
      )}
    </div>
  );
}

function EventCard({ event, onCancel }: {
  event: IrrigationEvent;
  onCancel: (id: string) => void;
}) {
  const sc = STATUS_COLORS[event.status] || '#6B7280';
  const progress = event.target_duration_minutes > 0
    ? Math.min(100, (event.actual_duration_minutes / event.target_duration_minutes) * 100)
    : 0;

  return (
    <div style={{
      padding: '16px', borderRadius: 14,
      background: `linear-gradient(135deg, ${sc}08, ${sc}04)`,
      border: `1px solid ${sc}25`,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        <span style={{
          padding: '3px 10px', borderRadius: 10, fontSize: 11, fontWeight: 700,
          background: `${sc}20`, color: sc,
        }}>
          {event.status} [SIMULATED]
        </span>
        <span style={{ color: '#E2E8F0', fontSize: 13, fontWeight: 600, flex: 1 }}>
          {SYSTEM_TYPE_LABELS[event.system_type]} — {event.zone_id}
        </span>
        <span style={{ fontSize: 11, color: '#64748B' }}>{event.device_id} (Simulated)</span>
      </div>

      {event.status === 'EXECUTING' && (
        <div style={{ marginBottom: 10 }}>
          <div style={{
            height: 6, borderRadius: 3, background: 'rgba(255,255,255,0.06)', overflow: 'hidden',
          }}>
            <div style={{
              height: '100%', borderRadius: 3, width: `${progress}%`,
              background: `linear-gradient(90deg, ${sc}, ${sc}CC)`,
              transition: 'width 1s ease',
            }} />
          </div>
          <div style={{ fontSize: 11, color: '#64748B', marginTop: 4 }}>
            {Math.round(progress)}% — {Math.round(event.actual_duration_minutes)}min / {event.target_duration_minutes}min (Simulated preview)
          </div>
        </div>
      )}

      <div style={{ display: 'flex', gap: 16, fontSize: 11, color: '#94A3B8' }}>
        <span>💧 {event.target_volume_mm}mm target</span>
        <span>📊 0 L physical delivered (Simulated preview)</span>
        <span>🤖 {event.automation_mode}</span>
      </div>

      {event.status === 'EXECUTING' && (
        <button onClick={() => onCancel(event.event_id)} style={{
          marginTop: 10, padding: '5px 14px', borderRadius: 8,
          border: '1px solid #EF444440', background: '#EF444410',
          color: '#EF4444', fontSize: 11, fontWeight: 600, cursor: 'pointer',
        }}>
          ⏹ Cancel (Local Preview)
        </button>
      )}
    </div>
  );
}

function WaterBudgetGauge({ budget }: { budget: { season_consumed_mm: number; season_quota_mm: number; daily_consumed_mm: number; daily_quota_mm: number; season_remaining_mm: number } }) {
  const pct = (budget.season_consumed_mm / budget.season_quota_mm) * 100;
  const dailyPct = (budget.daily_consumed_mm / budget.daily_quota_mm) * 100;
  const barColor = pct > 80 ? '#EF4444' : pct > 60 ? '#F59E0B' : '#22C55E';

  return (
    <div>
      <div style={{ fontSize: 12, color: '#94A3B8', marginBottom: 8 }}>Season Water Budget</div>
      <div style={{ height: 10, borderRadius: 5, background: 'rgba(255,255,255,0.06)', overflow: 'hidden', marginBottom: 6 }}>
        <div style={{ height: '100%', borderRadius: 5, width: `${pct}%`, background: barColor, transition: 'width 0.5s' }} />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#64748B' }}>
        <span>{budget.season_consumed_mm}mm used</span>
        <span>{budget.season_remaining_mm}mm left</span>
      </div>
      <div style={{ marginTop: 12, fontSize: 12, color: '#94A3B8' }}>Today</div>
      <div style={{ height: 6, borderRadius: 3, background: 'rgba(255,255,255,0.06)', overflow: 'hidden', marginTop: 4 }}>
        <div style={{ height: '100%', borderRadius: 3, width: `${dailyPct}%`, background: '#3B82F6' }} />
      </div>
      <div style={{ fontSize: 11, color: '#64748B', marginTop: 4 }}>
        {budget.daily_consumed_mm}mm / {budget.daily_quota_mm}mm
      </div>
    </div>
  );
}

/* ================================================================
   Main Dashboard
   ================================================================ */

export default function IrrigationDashboard() {
  const {
    fleet, activeEvents, pendingSchedule, waterBudget, safetyScore,
    isLoading, emergencyStopAll, approveSchedule, rejectSchedule,
    cancelEvent, setAutomationMode,
  } = useIrrigationState();

  const [tab, setTab] = useState<'overview' | 'schedule' | 'devices'>('overview');
  const [eStopNotice, setEStopNotice] = useState<string | null>(null);

  const onlineCount = fleet?.status_summary?.ONLINE || 0;
  const executingCount = fleet?.status_summary?.EXECUTING || 0;
  const offlineCount = fleet?.status_summary?.OFFLINE || (fleet?.total_actuators || 0);

  const handleEStop = async () => {
    await emergencyStopAll();
    setEStopNotice(
      "Physical actuator hardware is disconnected in the observation-only pilot. Emergency stop signal cannot be acknowledged by physical field equipment (fail-closed)."
    );
  };

  if (isLoading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 400, color: '#64748B' }}>
        Loading irrigation system…
      </div>
    );
  }

  return (
    <div style={{
      fontFamily: "'Inter', -apple-system, sans-serif",
      color: '#E2E8F0', maxWidth: 960, margin: '0 auto',
    }}>
      {/* Simulation / Disconnected Mode Banner */}
      <div
        role="alert"
        aria-label="Simulation mode banner"
        style={{
          background: 'rgba(239, 68, 68, 0.08)',
          border: '1px solid rgba(239, 68, 68, 0.3)',
          borderRadius: 12,
          padding: '12px 18px',
          marginBottom: 20,
          display: 'flex',
          alignItems: 'center',
          gap: 12,
        }}
      >
        <span style={{ fontSize: 22 }}>⚠️</span>
        <div>
          <div style={{ fontSize: 13, fontWeight: 700, color: '#F87171' }}>
            SIMULATION / OBSERVATION-ONLY MODE — NO PHYSICAL ACTUATOR HARDWARE CONNECTED
          </div>
          <div style={{ fontSize: 12, color: '#CBD5E1', marginTop: 2 }}>
            Physical irrigation actuators are not connected. All device counts, schedules, and flow metrics operate in preview simulation. Physical command dispatch is blocked fail-closed.
          </div>
        </div>
      </div>

      {eStopNotice && (
        <div
          role="status"
          style={{
            background: 'rgba(245, 158, 11, 0.1)',
            border: '1px solid rgba(245, 158, 11, 0.4)',
            borderRadius: 10,
            padding: '10px 16px',
            marginBottom: 16,
            fontSize: 12,
            color: '#FCD34D',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <span>🛑 {eStopNotice}</span>
          <button
            onClick={() => setEStopNotice(null)}
            style={{ background: 'transparent', border: 'none', color: '#FCD34D', cursor: 'pointer', fontWeight: 700, fontSize: 14 }}
          >
            ✕
          </button>
        </div>
      )}

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 22, fontWeight: 700, color: '#F1F5F9', display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <span>💧 Irrigation Control Center</span>
            <span style={{ fontSize: 11, fontWeight: 700, color: '#F87171', background: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.3)', padding: '2px 8px', borderRadius: 6 }}>
              SIMULATION / DISCONNECTED
            </span>
          </h2>
          <p style={{ margin: '4px 0 0', fontSize: 13, color: '#64748B' }}>
            Observation-Only Pilot · 0 Connected Actuators · {fleet?.total_zones || 0} zones
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <SafetyBadge score={safetyScore} />
          <button
            onClick={handleEStop}
            style={{
              padding: '8px 20px', borderRadius: 10, border: '2px solid #EF4444',
              background: '#EF444418', color: '#EF4444', fontSize: 13,
              fontWeight: 700, cursor: 'pointer', letterSpacing: 0.5,
            }}
          >
            🚨 E-STOP (Simulation)
          </button>
        </div>
      </div>

      {/* Stats Row */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 24 }}>
        <StatCard label="Online Actuators" value={onlineCount} accent="#6B7280" sub="No hardware connected" />
        <StatCard label="Executing" value={executingCount} accent="#6B7280" sub="Physical dispatch blocked" />
        <StatCard label="Offline / Disconnected" value={offlineCount} accent="#F59E0B" sub="All devices disconnected" />
        <StatCard
          label="Water Today"
          value="0 mm"
          accent="#06B6D4"
          sub="0 L delivered (Observation-only)"
        />
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 20, borderBottom: '1px solid rgba(255,255,255,0.06)', paddingBottom: 2 }}>
        {(['overview', 'schedule', 'devices'] as const).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              padding: '8px 20px', borderRadius: '8px 8px 0 0', border: 'none', cursor: 'pointer',
              background: tab === t ? 'rgba(59,130,246,0.12)' : 'transparent',
              color: tab === t ? '#60A5FA' : '#64748B',
              fontSize: 13, fontWeight: tab === t ? 700 : 500,
              borderBottom: tab === t ? '2px solid #3B82F6' : '2px solid transparent',
            }}
          >
            {t === 'overview' ? '📊 Overview' : t === 'schedule' ? '📅 Schedule' : '🔧 Devices'}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {tab === 'overview' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 20 }}>
          <div>
            <h3 style={{ fontSize: 15, fontWeight: 600, color: '#CBD5E1', marginBottom: 12 }}>
              Active Events
            </h3>
            {activeEvents.length === 0 ? (
              <div style={{ padding: 32, textAlign: 'center', color: '#64748B', fontSize: 13, background: 'rgba(255,255,255,0.02)', borderRadius: 12, border: '1px solid rgba(255,255,255,0.05)' }}>
                No active physical irrigation events (Actuator hardware disconnected in observation pilot)
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {activeEvents.map(e => (
                  <EventCard key={e.event_id} event={e} onCancel={cancelEvent} />
                ))}
              </div>
            )}

            <h3 style={{ fontSize: 15, fontWeight: 600, color: '#CBD5E1', margin: '24px 0 12px' }}>
              Pending Approvals
            </h3>
            {pendingSchedule.filter(s => s.approval_status === 'PENDING').length === 0 ? (
              <div style={{ padding: 24, textAlign: 'center', color: '#475569', fontSize: 13 }}>
                No pending approvals
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {pendingSchedule
                  .filter(s => s.approval_status === 'PENDING')
                  .map(s => (
                    <ScheduleRow key={s.schedule_id} entry={s} onApprove={approveSchedule} onReject={rejectSchedule} />
                  ))}
              </div>
            )}
          </div>

          <div>
            {waterBudget && <WaterBudgetGauge budget={waterBudget} />}
          </div>
        </div>
      )}

      {tab === 'schedule' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {pendingSchedule.map(s => (
            <ScheduleRow key={s.schedule_id} entry={s} onApprove={approveSchedule} onReject={rejectSchedule} />
          ))}
        </div>
      )}

      {tab === 'devices' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {fleet?.devices?.map(d => (
            <DeviceRow key={d.device_id} device={d} onModeChange={setAutomationMode} />
          ))}
        </div>
      )}
    </div>
  );
}
