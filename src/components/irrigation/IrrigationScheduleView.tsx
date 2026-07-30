'use client';

import React, { useMemo } from 'react';
import { useIrrigationState } from '@/hooks/useIrrigationState';
import { SYSTEM_TYPE_LABELS } from '@/lib/irrigation/types';
import type { IrrigationScheduleEntry } from '@/lib/irrigation/types';

/**
 * Timeline view for irrigation schedule entries.
 * Shows events grouped by date with weather overlay.
 */
export default function IrrigationScheduleView() {
  const { pendingSchedule, approveSchedule, rejectSchedule } = useIrrigationState();

  const grouped = useMemo(() => {
    const map = new Map<string, IrrigationScheduleEntry[]>();
    for (const entry of pendingSchedule) {
      const date = entry.scheduled_date;
      if (!map.has(date)) map.set(date, []);
      map.get(date)!.push(entry);
    }
    return Array.from(map.entries()).sort((a, b) => a[0].localeCompare(b[0]));
  }, [pendingSchedule]);

  const urgencyOrder: Record<string, number> = { CRITICAL: 0, HIGH: 1, NORMAL: 2, LOW: 3 };
  const urgencyColor: Record<string, string> = {
    CRITICAL: '#EF4444', HIGH: '#F59E0B', NORMAL: '#3B82F6', LOW: '#6B7280',
  };
  const statusColor: Record<string, string> = {
    PENDING: '#F59E0B', APPROVED: '#22C55E', REJECTED: '#EF4444', DEFERRED: '#F97316',
  };

  return (
    <div style={{ fontFamily: "'Inter', sans-serif", color: '#E2E8F0' }}>
      <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 20, color: '#F1F5F9' }}>
        📅 Irrigation Schedule
      </h3>

      {grouped.length === 0 && (
        <div style={{ textAlign: 'center', padding: 40, color: '#475569', fontSize: 13 }}>
          No scheduled events
        </div>
      )}

      {grouped.map(([date, entries]) => (
        <div key={date} style={{ marginBottom: 24 }}>
          <div style={{
            fontSize: 13, fontWeight: 600, color: '#94A3B8', marginBottom: 10,
            paddingBottom: 6, borderBottom: '1px solid rgba(255,255,255,0.06)',
          }}>
            {new Date(date).toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric' })}
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, paddingLeft: 16, borderLeft: '2px solid rgba(255,255,255,0.06)' }}>
            {entries
              .sort((a, b) => (urgencyOrder[a.urgency] ?? 2) - (urgencyOrder[b.urgency] ?? 2))
              .map(entry => {
                const uc = urgencyColor[entry.urgency] || '#6B7280';
                const sc = statusColor[entry.approval_status] || '#6B7280';
                return (
                  <div key={entry.schedule_id} style={{
                    padding: '12px 16px', borderRadius: 12,
                    background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)',
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                      <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 6, background: `${uc}20`, color: uc, fontWeight: 700 }}>
                        {entry.urgency}
                      </span>
                      <span style={{ flex: 1, fontSize: 13, fontWeight: 600, color: '#E2E8F0' }}>
                        {SYSTEM_TYPE_LABELS[entry.system_type]} — Zone {entry.zone_id}
                      </span>
                      <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 6, background: `${sc}20`, color: sc, fontWeight: 600 }}>
                        {entry.approval_status}
                      </span>
                    </div>
                    <div style={{ fontSize: 11, color: '#94A3B8' }}>{entry.reason}</div>
                    <div style={{ display: 'flex', gap: 12, marginTop: 6, fontSize: 11, color: '#64748B' }}>
                      <span>⏰ {entry.optimal_time}</span>
                      <span>💧 {entry.target_volume_mm}mm</span>
                      <span>⏱ {entry.target_duration_minutes}min</span>
                      {entry.rain_forecast_mm > 0 && <span>🌧 {entry.rain_forecast_mm}mm rain</span>}
                    </div>
                    {entry.approval_status === 'PENDING' && (
                      <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                        <button onClick={() => approveSchedule(entry.schedule_id)} style={{
                          padding: '4px 14px', borderRadius: 6, border: 'none',
                          background: '#22C55E', color: '#fff', fontSize: 11, fontWeight: 600, cursor: 'pointer',
                        }}>✓ Approve</button>
                        <button onClick={() => rejectSchedule(entry.schedule_id)} style={{
                          padding: '4px 14px', borderRadius: 6, border: '1px solid rgba(255,255,255,0.1)',
                          background: 'transparent', color: '#94A3B8', fontSize: 11, cursor: 'pointer',
                        }}>✕ Reject</button>
                      </div>
                    )}
                  </div>
                );
              })}
          </div>
        </div>
      ))}
    </div>
  );
}
