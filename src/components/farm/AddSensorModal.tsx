"use client";

import { useState } from "react";
import { Loader2, Wifi, X, Copy, Check } from "lucide-react";

interface AddSensorModalProps {
  plotId: string;
  onClose: () => void;
  onSuccess: () => void;
}

const SENSOR_TYPES = [
  { id: "MOISTURE", label: "Soil Moisture", desc: "Capacitive / resistive probes" },
  { id: "TEMP", label: "Temp & Humidity", desc: "DHT22, BME280, SHT31" },
  { id: "EC", label: "EC / Salinity", desc: "Electrical conductivity" },
  { id: "WEATHER", label: "Weather Station", desc: "Wind, rain, pressure" },
  { id: "OTHER", label: "Other", desc: "Custom telemetry" },
];

export default function AddSensorModal({ plotId, onClose, onSuccess }: AddSensorModalProps) {
  const [deviceId, setDeviceId] = useState("");
  const [type, setType] = useState("MOISTURE");
  const [vendor, setVendor] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<{ apiKey: string; deviceId: string } | null>(null);
  const [copied, setCopied] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!deviceId.trim()) {
      setError("Device ID is required.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const res = await fetch("/api/sensors/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plotId, deviceId: deviceId.trim(), type, vendor: vendor.trim() || undefined }),
      });

      const data = await res.json();

      if (res.ok && data.success) {
        setResult({ apiKey: data.apiKey, deviceId: data.deviceId });
      } else {
        setError(data.error || "Failed to register sensor.");
      }
    } catch {
      setError("Network error.");
    }

    setLoading(false);
  };

  const handleCopyKey = () => {
    if (result?.apiKey) {
      navigator.clipboard.writeText(result.apiKey);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleDone = () => {
    onSuccess();
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-white dark:bg-slate-900 rounded-xl shadow-2xl max-w-md w-full border border-slate-200 dark:border-slate-800 overflow-hidden">
        
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 dark:border-slate-800 flex justify-between items-center bg-slate-50 dark:bg-slate-950">
          <h3 className="font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-2">
            <Wifi size={18} className="text-indigo-500" />
            Register Sensor Device
          </h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors">
            <X size={20} />
          </button>
        </div>

        {!result ? (
          /* Registration Form */
          <form onSubmit={handleSubmit} className="p-6 space-y-4">
            
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">Device ID *</label>
              <input 
                type="text"
                value={deviceId}
                onChange={(e) => setDeviceId(e.target.value)}
                placeholder="e.g. ESP32-FIELD-A1"
                className="w-full px-4 py-2 border border-slate-300 dark:border-slate-700 rounded-lg bg-white dark:bg-slate-950 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-sm"
                autoFocus
              />
              <p className="text-xs text-slate-500 mt-1">Unique identifier for your device (printed on the board or configured in firmware).</p>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">Sensor Type</label>
              <div className="grid grid-cols-2 gap-2">
                {SENSOR_TYPES.map(t => (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => setType(t.id)}
                    className={`text-left p-2.5 rounded-lg border transition-all ${
                      type === t.id
                        ? "bg-indigo-50 dark:bg-indigo-900/20 border-indigo-500 text-indigo-700 dark:text-indigo-400"
                        : "border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800"
                    }`}
                  >
                    <span className="text-xs font-medium block">{t.label}</span>
                    <span className="text-[10px] text-slate-500 block mt-0.5">{t.desc}</span>
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">Vendor (Optional)</label>
              <input 
                type="text"
                value={vendor}
                onChange={(e) => setVendor(e.target.value)}
                placeholder="e.g. Espressif, Dragino, RAK"
                className="w-full px-4 py-2 border border-slate-300 dark:border-slate-700 rounded-lg bg-white dark:bg-slate-950 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-sm"
              />
            </div>

            {error && (
              <div className="p-3 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-sm rounded-lg">
                {error}
              </div>
            )}

            <div className="pt-2 flex justify-end gap-3">
              <button type="button" onClick={onClose} className="px-4 py-2 text-sm font-medium text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors">
                Cancel
              </button>
              <button type="submit" disabled={loading} className="px-6 py-2 text-sm font-medium bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg shadow-md hover:shadow-lg transition-all disabled:opacity-50 flex items-center gap-2">
                {loading && <Loader2 className="animate-spin" size={16} />}
                Register Device
              </button>
            </div>
          </form>
        ) : (
          /* Success — Show API Key */
          <div className="p-6 space-y-5">
            <div className="text-center">
              <div className="inline-flex p-3 rounded-full bg-green-100 dark:bg-green-900/30 text-green-600 dark:text-green-400 mb-3">
                <Check size={24} />
              </div>
              <h4 className="font-semibold text-slate-800 dark:text-slate-200">Device Registered!</h4>
              <p className="text-sm text-slate-500 mt-1">Configure your device with these credentials:</p>
            </div>

            <div className="space-y-3">
              <div className="p-3 bg-slate-50 dark:bg-slate-950 rounded-lg border border-slate-200 dark:border-slate-800">
                <p className="text-[10px] uppercase tracking-wider text-slate-400 mb-1">Device ID</p>
                <p className="text-sm font-mono text-slate-800 dark:text-slate-200">{result.deviceId}</p>
              </div>

              <div className="p-3 bg-slate-50 dark:bg-slate-950 rounded-lg border border-slate-200 dark:border-slate-800">
                <p className="text-[10px] uppercase tracking-wider text-slate-400 mb-1">API Key (save this — shown only once)</p>
                <div className="flex items-center gap-2">
                  <code className="text-sm font-mono text-indigo-600 dark:text-indigo-400 flex-1 break-all">{result.apiKey}</code>
                  <button
                    onClick={handleCopyKey}
                    className="p-1.5 rounded-md hover:bg-slate-200 dark:hover:bg-slate-800 transition-colors shrink-0"
                    title="Copy API key"
                  >
                    {copied ? <Check size={14} className="text-green-500" /> : <Copy size={14} className="text-slate-400" />}
                  </button>
                </div>
              </div>

              <div className="p-3 bg-blue-50 dark:bg-blue-900/10 rounded-lg border border-blue-200 dark:border-blue-900 text-xs text-blue-700 dark:text-blue-400">
                <p className="font-medium mb-1">Send data to:</p>
                <code className="text-[11px]">POST /api/sensors/ingest</code>
                <pre className="mt-1 whitespace-pre-wrap text-[10px] opacity-80">
{`{
  "deviceId": "${result.deviceId}",
  "apiKey": "${result.apiKey.substring(0, 8)}...",
  "temperature": 28.5,
  "humidity": 65,
  "soilMoisture": 42,
  "battery": 87,
  "rssi": -62
}`}
                </pre>
              </div>
            </div>

            <div className="pt-2 flex justify-end">
              <button onClick={handleDone} className="px-6 py-2 text-sm font-medium bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg shadow-md transition-all">
                Done
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
