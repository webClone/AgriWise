"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Wifi,
  WifiOff,
  Plus,
  Activity,
  Battery,
  BatteryLow,
  BatteryMedium,
  BatteryFull,
  Signal,
  Thermometer,
  Droplets,
  Wind,
  CloudRain,
  Zap,
  Trash2,
  Loader2,
} from "lucide-react";
import AddSensorModal from "./AddSensorModal";

interface SensorStatus {
  id: string;
  deviceId: string;
  type: string;
  vendor: string | null;
  status: string;
  isOnline: boolean;
  battery: number | null;
  rssi: number | null;
  signalQuality: string;
  lastSync: string | null;
  createdAt: string;
  latestReading: {
    temperature: number | null;
    humidity: number | null;
    soilMoisture: number | null;
    ec: number | null;
    windSpeed: number | null;
    rainfall: number | null;
    timestamp: string;
  } | null;
}

interface SensorListProps {
  plotId: string;
  sensors: any[];
}

const POLL_INTERVAL = 15000; // 15 seconds

function getRelativeTime(dateStr: string | null): string {
  if (!dateStr) return "Never";
  const diff = Date.now() - new Date(dateStr).getTime();
  const seconds = Math.floor(diff / 1000);
  if (seconds < 10) return "Just now";
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function getBatteryIcon(level: number | null) {
  if (level == null) return <Battery size={14} className="text-slate-400" />;
  if (level < 20) return <BatteryLow size={14} className="text-red-500" />;
  if (level < 50) return <BatteryMedium size={14} className="text-amber-500" />;
  return <BatteryFull size={14} className="text-green-500" />;
}

function getBatteryColor(level: number | null) {
  if (level == null) return "text-slate-400";
  if (level < 20) return "text-red-500";
  if (level < 50) return "text-amber-500";
  return "text-green-500";
}

function getSignalColor(quality: string) {
  switch (quality) {
    case "Excellent": return "text-green-500";
    case "Good": return "text-emerald-500";
    case "Fair": return "text-amber-500";
    case "Weak": return "text-red-500";
    default: return "text-slate-400";
  }
}

function getTypeLabel(type: string) {
  switch (type) {
    case "MOISTURE": return "Soil Moisture";
    case "TEMP": return "Temp & Humidity";
    case "EC": return "EC / Salinity";
    case "WEATHER": return "Weather Station";
    default: return type;
  }
}

function getTypeIcon(type: string) {
  switch (type) {
    case "MOISTURE": return <Droplets size={20} />;
    case "TEMP": return <Thermometer size={20} />;
    case "EC": return <Zap size={20} />;
    case "WEATHER": return <Wind size={20} />;
    default: return <Activity size={20} />;
  }
}

export default function SensorList({ plotId, sensors: initialSensors }: SensorListProps) {
  const [sensorStatuses, setSensorStatuses] = useState<SensorStatus[]>([]);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [isInitialLoad, setIsInitialLoad] = useState(true);

  const fetchStatuses = useCallback(async () => {
    try {
      const res = await fetch(`/api/plots/${plotId}/sensors/status`);
      if (res.ok) {
        const data = await res.json();
        setSensorStatuses(data.sensors || []);
      }
    } catch (err) {
      console.error("Failed to poll sensor statuses:", err);
    }
    setIsInitialLoad(false);
  }, [plotId]);

  // Initial fetch + polling
  useEffect(() => {
    fetchStatuses();
    const interval = setInterval(fetchStatuses, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchStatuses]);

  const handleDelete = async (sensorId: string) => {
    if (!confirm("Remove this sensor? All its readings will be deleted.")) return;
    setDeletingId(sensorId);
    try {
      const res = await fetch(`/api/sensors/${sensorId}`, { method: "DELETE" });
      if (res.ok) {
        setSensorStatuses((prev) => prev.filter((s) => s.id !== sensorId));
      } else {
        alert("Failed to remove sensor.");
      }
    } catch {
      alert("Network error.");
    }
    setDeletingId(null);
  };

  const handleSuccess = () => {
    fetchStatuses(); // Refresh immediately after adding
  };

  // If initial data hasn't loaded from API yet, use static data from props
  const displaySensors = isInitialLoad
    ? initialSensors.map((s) => ({
        id: s.id,
        deviceId: s.deviceId,
        type: s.type,
        vendor: s.vendor,
        status: s.status || "OFFLINE",
        isOnline: s.status === "ACTIVE",
        battery: s.battery ?? null,
        rssi: s.rssi ?? null,
        signalQuality: "None",
        lastSync: s.lastSync,
        createdAt: s.createdAt,
        latestReading: null,
      }))
    : sensorStatuses;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <h3 className="font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-2">
          <Wifi className="text-indigo-500" size={18} />
          Connected Sensors
          {displaySensors.length > 0 && (
            <span className="text-xs font-normal text-slate-400 ml-1">
              ({displaySensors.filter((s) => s.isOnline).length}/{displaySensors.length} online)
            </span>
          )}
        </h3>
        <button
          onClick={() => setIsModalOpen(true)}
          className="flex items-center gap-1.5 text-xs font-medium bg-indigo-50 dark:bg-indigo-900/20 text-indigo-700 dark:text-indigo-400 px-3 py-1.5 rounded-full border border-indigo-100 dark:border-indigo-800 hover:bg-indigo-100 dark:hover:bg-indigo-900/40 transition-colors"
        >
          <Plus size={14} />
          Add Device
        </button>
      </div>

      {/* Sensor Cards */}
      <div className="space-y-3">
        {displaySensors.length > 0 ? (
          displaySensors.map((sensor) => (
            <div
              key={sensor.id}
              className={`relative p-4 rounded-xl border shadow-sm transition-all hover:shadow-md ${
                sensor.isOnline
                  ? "border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900"
                  : "border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 opacity-75"
              }`}
            >
              <div className="flex items-start justify-between">
                {/* Left: Sensor Info */}
                <div className="flex items-start gap-3 flex-1 min-w-0">
                  {/* Type Icon */}
                  <div
                    className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 ${
                      sensor.isOnline
                        ? "bg-indigo-100 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400"
                        : "bg-slate-100 dark:bg-slate-800 text-slate-400"
                    }`}
                  >
                    {getTypeIcon(sensor.type)}
                  </div>

                  <div className="min-w-0 flex-1">
                    {/* Title Row */}
                    <div className="flex items-center gap-2 flex-wrap">
                      <h4 className="text-sm font-semibold text-slate-800 dark:text-slate-200">
                        {getTypeLabel(sensor.type)}
                      </h4>
                      <span className="text-[10px] font-mono text-slate-400 px-1.5 py-0.5 bg-slate-100 dark:bg-slate-800 rounded">
                        {sensor.deviceId}
                      </span>
                      {sensor.vendor && (
                        <span className="text-[10px] text-slate-400">{sensor.vendor}</span>
                      )}
                    </div>

                    {/* Meta Row: Battery, Signal, Last Sync */}
                    <div className="flex items-center gap-4 mt-1.5 text-xs text-slate-500 dark:text-slate-400 flex-wrap">
                      {/* Battery */}
                      <span className="flex items-center gap-1">
                        {getBatteryIcon(sensor.battery)}
                        <span className={getBatteryColor(sensor.battery)}>
                          {sensor.battery != null ? `${Math.round(sensor.battery)}%` : "N/A"}
                        </span>
                      </span>

                      {/* Signal */}
                      <span className="flex items-center gap-1">
                        <Signal size={12} className={getSignalColor(sensor.signalQuality)} />
                        <span className={getSignalColor(sensor.signalQuality)}>
                          {sensor.signalQuality}
                          {sensor.rssi != null && (
                            <span className="text-slate-400 ml-1">({sensor.rssi} dBm)</span>
                          )}
                        </span>
                      </span>

                      {/* Last Sync */}
                      <span className="flex items-center gap-1">
                        <Activity size={12} />
                        {getRelativeTime(sensor.lastSync)}
                      </span>
                    </div>

                    {/* Latest Readings */}
                    {sensor.latestReading && (
                      <div className="flex items-center gap-3 mt-2.5 flex-wrap">
                        {sensor.latestReading.temperature != null && (
                          <span className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-md bg-orange-50 dark:bg-orange-900/10 text-orange-700 dark:text-orange-400 border border-orange-100 dark:border-orange-900/30">
                            <Thermometer size={12} />
                            {sensor.latestReading.temperature.toFixed(1)}°C
                          </span>
                        )}
                        {sensor.latestReading.humidity != null && (
                          <span className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-md bg-blue-50 dark:bg-blue-900/10 text-blue-700 dark:text-blue-400 border border-blue-100 dark:border-blue-900/30">
                            <Droplets size={12} />
                            {sensor.latestReading.humidity.toFixed(1)}%
                          </span>
                        )}
                        {sensor.latestReading.soilMoisture != null && (
                          <span className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-md bg-emerald-50 dark:bg-emerald-900/10 text-emerald-700 dark:text-emerald-400 border border-emerald-100 dark:border-emerald-900/30">
                            <Droplets size={12} />
                            {sensor.latestReading.soilMoisture.toFixed(1)}%
                          </span>
                        )}
                        {sensor.latestReading.ec != null && (
                          <span className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-md bg-purple-50 dark:bg-purple-900/10 text-purple-700 dark:text-purple-400 border border-purple-100 dark:border-purple-900/30">
                            <Zap size={12} />
                            {sensor.latestReading.ec.toFixed(2)} mS/cm
                          </span>
                        )}
                        {sensor.latestReading.windSpeed != null && (
                          <span className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-md bg-sky-50 dark:bg-sky-900/10 text-sky-700 dark:text-sky-400 border border-sky-100 dark:border-sky-900/30">
                            <Wind size={12} />
                            {sensor.latestReading.windSpeed.toFixed(1)} km/h
                          </span>
                        )}
                        {sensor.latestReading.rainfall != null && (
                          <span className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-md bg-cyan-50 dark:bg-cyan-900/10 text-cyan-700 dark:text-cyan-400 border border-cyan-100 dark:border-cyan-900/30">
                            <CloudRain size={12} />
                            {sensor.latestReading.rainfall.toFixed(1)} mm
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </div>

                {/* Right: Status + Delete */}
                <div className="flex flex-col items-end gap-2 ml-4 shrink-0">
                  <div className="flex items-center gap-1.5">
                    {sensor.isOnline ? (
                      <>
                        <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                        <span className="text-xs font-medium text-green-600 dark:text-green-400">Online</span>
                      </>
                    ) : (
                      <>
                        <WifiOff size={12} className="text-slate-400" />
                        <span className="text-xs font-medium text-slate-400">Offline</span>
                      </>
                    )}
                  </div>
                  <button
                    onClick={() => handleDelete(sensor.id)}
                    disabled={deletingId === sensor.id}
                    className="p-1 rounded-md text-slate-300 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/10 transition-colors disabled:opacity-50"
                    title="Remove sensor"
                  >
                    {deletingId === sensor.id ? (
                      <Loader2 className="animate-spin" size={14} />
                    ) : (
                      <Trash2 size={14} />
                    )}
                  </button>
                </div>
              </div>
            </div>
          ))
        ) : (
          <div className="text-center py-10 rounded-xl border border-dashed border-slate-300 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50">
            <div className="inline-flex p-3 rounded-full bg-slate-100 dark:bg-slate-900 text-slate-400 mb-3">
              <Wifi size={24} />
            </div>
            <p className="text-slate-500 dark:text-slate-400 text-sm font-medium">
              No sensors connected
            </p>
            <p className="text-slate-400 dark:text-slate-500 text-xs mt-1">
              Register a device to start receiving telemetry data.
            </p>
            <button
              onClick={() => setIsModalOpen(true)}
              className="mt-4 text-xs text-indigo-600 hover:text-indigo-700 font-medium underline underline-offset-2"
            >
              Register first sensor
            </button>
          </div>
        )}
      </div>

      {/* Polling indicator */}
      {displaySensors.length > 0 && (
        <p className="text-[10px] text-slate-400 text-right">
          Auto-refreshing every {POLL_INTERVAL / 1000}s
        </p>
      )}

      {/* Add Sensor Modal */}
      {isModalOpen && (
        <AddSensorModal
          plotId={plotId}
          onClose={() => setIsModalOpen(false)}
          onSuccess={handleSuccess}
        />
      )}
    </div>
  );
}
