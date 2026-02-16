"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Wifi,
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
  ChevronRight,
  AlertTriangle,
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
  return `${days} day${days > 1 ? "s" : ""} ago`;
}

function getOfflineTag(sensor: any) {
  if (sensor.isOnline) return null;
  
  if (!sensor.lastSync) return { label: "Never connected", color: "text-slate-400", dot: "bg-slate-300" };
  
  if (sensor.battery != null && sensor.battery < 20) {
    return { label: "Low battery", color: "text-red-500 font-bold", dot: "bg-red-500" };
  }

  const diffMs = Date.now() - new Date(sensor.lastSync).getTime();
  const diffHours = diffMs / (1000 * 60 * 60);
  
  if (diffHours > 6) {
    return { label: "No data 6h+", color: "text-amber-500", dot: "bg-amber-400" };
  }
  
  return { label: "Offline", color: "text-slate-400", dot: "bg-slate-300" };
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

function getSensorBenefits(type: string) {
  switch (type) {
    case "MOISTURE":
      return [
        "Irrigation scheduling precision",
        "Drought risk detection",
        "Root zone modeling"
      ];
    case "TEMP":
        return [
            "Frost prediction accuracy",
            "Growing degree days tracking",
            "Disease risk modeling"
        ];
    case "EC":
        return [
            "Salinity stress alerts",
            "Fertilizer efficiency tracking",
            "Yield loss prevention"
        ];
    case "WEATHER":
        return [
            "Hyper-local forecast",
            "Spray window optimization",
            "Evapotranspiration (ET0) calc"
        ];
    default: return ["Improves overall model accuracy"];
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
              className={`relative p-4 rounded-xl border shadow-sm transition-all group cursor-pointer ${
                sensor.isOnline
                  ? "border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:border-indigo-300 dark:hover:border-indigo-700 hover:shadow-md"
                  : "border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 opacity-75 hover:opacity-100"
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
                      <span className="flex items-center gap-1 font-medium text-slate-400 dark:text-slate-500">
                        <Activity size={12} className="opacity-70" />
                        Last seen: {getRelativeTime(sensor.lastSync)}
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
                      (() => {
                        const tag = getOfflineTag(sensor);
                        return (
                          <div className="flex flex-col items-end gap-1">
                            <div className="flex items-center gap-1.5">
                              <div className={`w-1.5 h-1.5 rounded-full ${tag?.dot || "bg-slate-300"}`} />
                              <span className={`text-[10px] uppercase font-bold tracking-wider ${tag?.color || "text-slate-400"}`}>
                                {tag?.label || "Offline"}
                              </span>
                            </div>
                            {tag?.label === "Never Connected" ? (
                                <p className="text-[9px] text-indigo-500 cursor-pointer hover:underline text-right leading-tight">
                                    Connect to enable<br/>dynamic irrigation alerts
                                </p>
                            ) : (
                                <span className="text-[9px] font-medium text-amber-500/80 bg-amber-500/5 px-1.5 py-0.5 rounded border border-amber-500/10 flex items-center gap-1">
                                    <AlertTriangle size={8} /> Data confidence: Low
                                </span>
                            )}
                          
                          {/* Benefits List for Disconnected Sensors */}
                          {!sensor.isOnline && tag?.label === "Never Connected" && (
                              <div className="mt-2 pt-2 border-t border-slate-100 dark:border-slate-800 w-full">
                                  <p className="text-[9px] font-bold text-slate-400 uppercase tracking-tight mb-1">
                                      Connect to unlock:
                                  </p>
                                  <ul className="space-y-0.5">
                                      {getSensorBenefits(sensor.type).map((benefit, idx) => (
                                          <li key={idx} className="flex items-center gap-1 text-[9px] text-slate-500">
                                              <div className="w-1 h-1 rounded-full bg-indigo-400"></div>
                                              {benefit}
                                          </li>
                                      ))}
                                  </ul>
                              </div>
                          )}
                          
                          {/* Consequence Warning for Moisture Sensors */}
                          {!sensor.isOnline && sensor.type === "MOISTURE" && (
                              <div className="mt-2 text-[9px] font-medium text-amber-600 dark:text-amber-500 flex items-start gap-1 p-1.5 bg-amber-50 dark:bg-amber-900/10 rounded border border-amber-100 dark:border-amber-800/30 leading-tight">
                                  <AlertTriangle size={10} className="shrink-0 mt-0.5" />
                                  <span>Irrigation recommendations currently use satellite evapotranspiration models. Live soil data would increase precision.</span>
                              </div>
                          )}
                        </div>
                      );
                      })()
                    )}
                  </div>
                  
                  <div className="flex items-center gap-2 mt-auto">
                      <span className="text-[10px] font-bold text-indigo-500 opacity-0 group-hover:opacity-100 transition-opacity uppercase tracking-widest translate-x-1 group-hover:translate-x-0 transform duration-300">
                        View Details
                      </span>
                      <ChevronRight size={14} className="text-slate-300 group-hover:text-indigo-400 transition-colors" />
                      
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDelete(sensor.id);
                        }}
                        disabled={deletingId === sensor.id}
                        className="p-1 rounded-md text-slate-300 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/10 transition-colors disabled:opacity-50 ml-1"
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
