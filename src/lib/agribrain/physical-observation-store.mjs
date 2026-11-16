/**
 * Akaloris W2 Physical IoT Observation Store & Ingestion Engine (ESM runtime)
 */

import {
  PHYSICAL_VARIABLE_LIMITS,
  STANDARD_SOIL_PROFILE_DEPTHS_CM,
  computeRawPayloadHash,
  normalizeRawReading,
  buildSoilDepthProfile,
} from "./physical-sensor-contract.mjs";

class PhysicalObservationStore {
  constructor() {
    this.observationsByPlot = new Map();
    this.quarantinedList = [];
    this.seenMessageIds = new Set();
    this.seenPayloadHashes = new Set();
    this.calibrationProfiles = new Map();
    this.channelLastSeen = new Map();
  }

  reset() {
    this.observationsByPlot.clear();
    this.quarantinedList = [];
    this.seenMessageIds.clear();
    this.seenPayloadHashes.clear();
    this.calibrationProfiles.clear();
    this.channelLastSeen.clear();
  }

  registerCalibration(deviceId, calibration) {
    this.calibrationProfiles.set(deviceId, calibration);
  }

  checkCalibration(deviceId, asOfDate) {
    const profile = this.calibrationProfiles.get(deviceId);
    if (!profile) {
      return { isValid: false, isExpired: false };
    }
    if (profile.validUntil) {
      const expiresAt = new Date(profile.validUntil);
      if (asOfDate.getTime() > expiresAt.getTime()) {
        return { isValid: false, isExpired: true, profile: { ...profile, isExpired: true } };
      }
    }
    return { isValid: true, isExpired: false, profile };
  }

  ingestPayload(input, options = {}) {
    const serverReceivedAt = new Date().toISOString();
    const rawPayloadHash = computeRawPayloadHash(options.rawPayloadForHash ?? input);

    // 1. Replay & Idempotence Check
    if (input.messageId && this.seenMessageIds.has(input.messageId)) {
      return {
        success: true,
        replayed: true,
        deviceId: input.deviceId,
        rawPayloadHash,
        serverReceivedAt,
        deviceAcquiredAt: input.deviceAcquiredAt || serverReceivedAt,
        accepted: [],
        quarantined: [],
        message: "Duplicate message detected (messageId match); idempotent return",
      };
    }

    const payloadSignature = `${input.deviceId}:${input.deviceAcquiredAt || ""}:${rawPayloadHash}`;
    if (this.seenPayloadHashes.has(payloadSignature)) {
      return {
        success: true,
        replayed: true,
        deviceId: input.deviceId,
        rawPayloadHash,
        serverReceivedAt,
        deviceAcquiredAt: input.deviceAcquiredAt || serverReceivedAt,
        accepted: [],
        quarantined: [],
        message: "Duplicate payload detected (provenance hash match); idempotent return",
      };
    }

    // 2. Acquisition timestamp validation
    let deviceAcquiredAt = input.deviceAcquiredAt;
    if (!deviceAcquiredAt) {
      deviceAcquiredAt = serverReceivedAt;
    } else {
      const parsedTime = Date.parse(deviceAcquiredAt);
      if (isNaN(parsedTime)) {
        throw new Error("deviceAcquiredAt must be a valid ISO 8601 UTC timestamp");
      }
      const now = Date.now();
      if (parsedTime > now + 300_000) {
        throw new Error("deviceAcquiredAt cannot be in the future (clock drift violation)");
      }
    }

    const acqDate = new Date(deviceAcquiredAt);
    const plotId = options.registeredPlotId || input.plotId || "default_plot";

    // 3. Mark message seen
    if (input.messageId) {
      this.seenMessageIds.add(input.messageId);
    }
    this.seenPayloadHashes.add(payloadSignature);

    // 4. Calibration status
    const calStatus = this.checkCalibration(input.deviceId, acqDate);

    // 5. Expand readings
    const itemsToProcess = [];

    if (Array.isArray(input.readings) && input.readings.length > 0) {
      itemsToProcess.push(...input.readings);
    } else {
      const nominalDepth = input.depthCm ?? 15;
      if (input.soilMoisture != null) {
        itemsToProcess.push({
          channelId: input.channelId || `ch_soil_moisture_${nominalDepth}cm`,
          variable: "soil_moisture_vwc",
          rawValue: input.soilMoisture,
          rawUnit: "pct",
          depthCm: nominalDepth,
          calibrationId: input.calibrationId,
        });
      }
      if (input.temperature != null) {
        itemsToProcess.push({
          channelId: `ch_temperature_${nominalDepth}cm`,
          variable: "soil_temperature_c",
          rawValue: input.temperature,
          rawUnit: "celsius",
          depthCm: nominalDepth,
        });
      }
      if (input.ec != null) {
        itemsToProcess.push({
          channelId: `ch_ec_${nominalDepth}cm`,
          variable: "soil_ec_ds_m",
          rawValue: input.ec,
          rawUnit: "ds_m",
          depthCm: nominalDepth,
        });
      }
      if (input.humidity != null) {
        itemsToProcess.push({
          channelId: "ch_humidity",
          variable: "relative_humidity_pct",
          rawValue: input.humidity,
          rawUnit: "pct",
        });
      }
      if (input.rainfall != null) {
        itemsToProcess.push({
          channelId: "ch_rainfall",
          variable: "rainfall_mm",
          rawValue: input.rainfall,
          rawUnit: "mm",
        });
      }
      if (input.windSpeed != null) {
        itemsToProcess.push({
          channelId: "ch_wind_speed",
          variable: "wind_speed_ms",
          rawValue: input.windSpeed,
          rawUnit: "m_s",
        });
      }
    }

    const accepted = [];
    const quarantined = [];

    for (let i = 0; i < itemsToProcess.length; i++) {
      const item = itemsToProcess[i];
      const channelId = item.channelId || `ch_${i + 1}`;
      const variable = item.variable || "soil_moisture_vwc";
      const rawValue = item.rawValue;

      if (typeof rawValue !== "number" || !Number.isFinite(rawValue)) {
        const q = {
          quarantineId: `quar-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
          deviceId: input.deviceId,
          channelId,
          plotId,
          variable,
          rawValue,
          reason: "Telemetry rawValue must be a finite number",
          rawPayloadHash,
          quarantinedAt: serverReceivedAt,
          deviceAcquiredAt,
        };
        quarantined.push(q);
        this.quarantinedList.push(q);
        continue;
      }

      const isSoilVar = typeof variable === "string" && variable.startsWith("soil_");
      if (isSoilVar) {
        if (item.depthCm != null && (item.depthCm <= 0 || item.depthCm > 300)) {
          const q = {
            quarantineId: `quar-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
            deviceId: input.deviceId,
            channelId,
            plotId,
            variable,
            rawValue,
            reason: `incorrect_depth_registration: depthCm ${item.depthCm} is invalid (must be > 0 and <= 300 cm)`,
            rawPayloadHash,
            quarantinedAt: serverReceivedAt,
            deviceAcquiredAt,
          };
          quarantined.push(q);
          this.quarantinedList.push(q);
          continue;
        }
      }

      const normalized = normalizeRawReading({
        deviceId: input.deviceId,
        channelId,
        plotId,
        variable,
        rawValue,
        rawUnit: item.rawUnit || "pct",
        nominalDepthCm: item.depthCm,
        deviceAcquiredAt,
        serverReceivedAt,
        calibration: calStatus.profile,
      });

      if (PHYSICAL_VARIABLE_LIMITS[variable]) {
        const [minVal, maxVal] = PHYSICAL_VARIABLE_LIMITS[variable];
        if (normalized.normalizedValue < minVal || normalized.normalizedValue > maxVal) {
          const q = {
            quarantineId: `quar-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
            deviceId: input.deviceId,
            channelId,
            plotId,
            variable,
            rawValue,
            reason: `out_of_physical_range: value ${normalized.normalizedValue} outside [${minVal}, ${maxVal}] for ${variable}`,
            rawPayloadHash,
            quarantinedAt: serverReceivedAt,
            deviceAcquiredAt,
          };
          quarantined.push(q);
          this.quarantinedList.push(q);
          continue;
        }
      }

      let qaState = normalized.qaState;
      if (calStatus.isExpired) {
        qaState = "SUSPECT";
      }

      const finalRecord = {
        ...normalized,
        qaState,
        provenance: {
          ...normalized.provenance,
          rawPayloadHash,
        },
      };

      accepted.push(finalRecord);

      const channelKey = `${input.deviceId}:${channelId}`;
      this.channelLastSeen.set(channelKey, {
        lastSeen: acqDate,
        latestValue: finalRecord.normalizedValue,
        unit: finalRecord.normalizedUnit,
        variable: finalRecord.variable,
        depthCm: finalRecord.depthInterval?.nominalCm,
      });

      let plotList = this.observationsByPlot.get(plotId);
      if (!plotList) {
        plotList = [];
        this.observationsByPlot.set(plotId, plotList);
      }
      plotList.push(finalRecord);
    }

    return {
      success: true,
      replayed: false,
      deviceId: input.deviceId,
      rawPayloadHash,
      serverReceivedAt,
      deviceAcquiredAt,
      accepted,
      quarantined,
    };
  }

  getObservationsForPlot(plotId, options = {}) {
    const list = this.observationsByPlot.get(plotId) || [];
    let filtered = [...list];

    if (options.deviceId) {
      filtered = filtered.filter((r) => r.deviceId === options.deviceId);
    }
    if (options.variable) {
      filtered = filtered.filter((r) => r.variable === options.variable);
    }
    if (options.since) {
      const sinceMs = Date.parse(options.since);
      if (!isNaN(sinceMs)) {
        filtered = filtered.filter((r) => Date.parse(r.deviceAcquiredAt) >= sinceMs);
      }
    }

    filtered.sort((a, b) => Date.parse(b.deviceAcquiredAt) - Date.parse(a.deviceAcquiredAt));

    if (options.limit && options.limit > 0) {
      filtered = filtered.slice(0, options.limit);
    }

    return filtered;
  }

  getChannelsForDevice(deviceId, asOfDate = new Date()) {
    const channels = [];
    const OFFLINE_MS = 45 * 60 * 1000;
    const STALE_MS = 15 * 60 * 1000;

    const calStatus = this.checkCalibration(deviceId, asOfDate);

    for (const [key, val] of this.channelLastSeen.entries()) {
      if (key.startsWith(`${deviceId}:`)) {
        const channelId = key.split(":")[1];
        const ageMs = asOfDate.getTime() - val.lastSeen.getTime();

        let freshness = "FRESH";
        let status = "ACTIVE";

        if (ageMs > OFFLINE_MS) {
          status = "OFFLINE";
          freshness = "OFFLINE";
        } else if (ageMs > STALE_MS) {
          freshness = "STALE";
        }

        channels.push({
          channelId,
          deviceId,
          variable: val.variable,
          depthCm: val.depthCm,
          status,
          freshness,
          calibrationStatus: calStatus.isExpired ? "EXPIRED" : calStatus.isValid ? "VALID" : "UNREGISTERED",
          lastSeen: val.lastSeen.toISOString(),
          latestNormalizedValue: val.latestValue,
          latestUnit: val.unit,
        });
      }
    }

    return channels;
  }

  getSoilDepthProfile(plotId, deviceId, options = {}) {
    const readings = this.getObservationsForPlot(plotId, {
      deviceId,
      variable: "soil_moisture_vwc",
    });

    const latestByDepth = new Map();
    for (const r of readings) {
      const depth = r.depthInterval?.nominalCm ?? 15;
      if (!latestByDepth.has(depth)) {
        latestByDepth.set(depth, r);
      }
    }

    const recordsForProfile = Array.from(latestByDepth.values());

    return buildSoilDepthProfile(recordsForProfile, {
      plotId,
      deviceId,
      timestamp: options.asOfTimestamp || (recordsForProfile[0]?.deviceAcquiredAt ?? new Date().toISOString()),
    });
  }

  getQuarantined(plotId) {
    if (plotId) {
      return this.quarantinedList.filter((q) => q.plotId === plotId);
    }
    return [...this.quarantinedList];
  }
}

export const physicalObservationStore = new PhysicalObservationStore();
