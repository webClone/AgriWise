/**
 * Akaloris W2 Physical IoT Intelligence & Multi-Depth Observation Contract (ESM)
 */

import crypto from "crypto";

export const PHYSICAL_VARIABLE_LIMITS = Object.freeze({
  soil_moisture_vwc: [0.0, 0.75],
  soil_water_tension_kpa: [0.0, 2000.0],
  soil_temperature_c: [-20.0, 70.0],
  soil_ec_ds_m: [0.0, 30.0],
  soil_ph: [3.0, 11.0],
  air_temperature_c: [-50.0, 60.0],
  relative_humidity_pct: [0.0, 100.0],
  dew_point_c: [-50.0, 50.0],
  vpd_kpa: [0.0, 10.0],
  rainfall_mm: [0.0, 500.0],
  rain_rate_mm_h: [0.0, 500.0],
  wind_speed_ms: [0.0, 75.0],
  wind_gust_ms: [0.0, 100.0],
  wind_direction_deg: [0.0, 360.0],
  solar_radiation_w_m2: [0.0, 2000.0],
  par_umol_m2_s: [0.0, 4000.0],
  leaf_wetness: [0.0, 1.0],
  battery_pct: [0.0, 100.0],
  battery_voltage_v: [0.0, 15.0],
  signal_rssi_dbm: [-140.0, 0.0],
  signal_snr_db: [-30.0, 30.0],
});

export const STANDARD_SOIL_PROFILE_DEPTHS_CM = Object.freeze([
  10, 15, 30, 45, 60, 90,
]);

export function computeRawPayloadHash(payload) {
  const jsonStr = typeof payload === "string" ? payload : JSON.stringify(payload);
  return crypto.createHash("sha256").update(jsonStr, "utf8").digest("hex");
}

export function validatePhysicalObservation(record) {
  const errors = [];
  if (!record || typeof record !== "object") {
    return { valid: false, errors: ["Observation record must be a non-null object"] };
  }

  if (!record.readingId || typeof record.readingId !== "string") {
    errors.push("readingId must be a non-empty string");
  }
  if (!record.deviceId || typeof record.deviceId !== "string") {
    errors.push("deviceId must be a non-empty string");
  }
  if (!record.channelId || typeof record.channelId !== "string") {
    errors.push("channelId must be a non-empty string");
  }
  if (!record.plotId || typeof record.plotId !== "string") {
    errors.push("plotId must be a non-empty string");
  }
  if (!record.variable || !Object.prototype.hasOwnProperty.call(PHYSICAL_VARIABLE_LIMITS, record.variable)) {
    errors.push(`variable must be one of canonical variables, received: ${String(record.variable)}`);
  }
  if (typeof record.rawValue !== "number" || !Number.isFinite(record.rawValue)) {
    errors.push("rawValue must be a finite number");
  }
  if (typeof record.normalizedValue !== "number" || !Number.isFinite(record.normalizedValue)) {
    errors.push("normalizedValue must be a finite number");
  }

  if (!record.deviceAcquiredAt || isNaN(Date.parse(record.deviceAcquiredAt))) {
    errors.push("deviceAcquiredAt must be a valid ISO 8601 UTC timestamp");
  } else {
    const acqTime = Date.parse(record.deviceAcquiredAt);
    const now = Date.now();
    if (acqTime > now + 300_000) {
      errors.push("deviceAcquiredAt cannot be in the future (clock drift violation)");
    }
  }

  if (!record.serverReceivedAt || isNaN(Date.parse(record.serverReceivedAt))) {
    errors.push("serverReceivedAt must be a valid ISO 8601 UTC timestamp");
  }

  if (!record.provenance?.rawPayloadHash || typeof record.provenance.rawPayloadHash !== "string") {
    errors.push("provenance.rawPayloadHash must be a non-empty hex hash string");
  }

  if (record.variable && Object.prototype.hasOwnProperty.call(PHYSICAL_VARIABLE_LIMITS, record.variable)) {
    const [minVal, maxVal] = PHYSICAL_VARIABLE_LIMITS[record.variable];
    if (record.normalizedValue != null && (record.normalizedValue < minVal || record.normalizedValue > maxVal)) {
      errors.push(`normalizedValue ${record.normalizedValue} is out of physical range [${minVal}, ${maxVal}] for ${record.variable}`);
    }
  }

  return { valid: errors.length === 0, errors };
}

export function normalizeRawReading(input) {
  const deviceAcquiredAt = input.deviceAcquiredAt || new Date().toISOString();
  const serverReceivedAt = input.serverReceivedAt || new Date().toISOString();
  const rawPayload = input.rawPayload ?? {
    deviceId: input.deviceId,
    channelId: input.channelId,
    variable: input.variable,
    value: input.rawValue,
    unit: input.rawUnit,
    acquiredAt: deviceAcquiredAt,
  };
  const rawPayloadHash = computeRawPayloadHash(rawPayload);

  let normalizedValue = input.rawValue;
  let normalizedUnit = input.rawUnit;

  if (input.variable === "soil_moisture_vwc") {
    normalizedUnit = "fraction";
    if (input.rawValue > 1.0) {
      normalizedValue = Number((input.rawValue / 100).toFixed(4));
    } else {
      normalizedValue = Number(input.rawValue.toFixed(4));
    }
  } else if (input.variable === "soil_temperature_c" || input.variable === "air_temperature_c") {
    normalizedUnit = "celsius";
    if (input.rawUnit === "fahrenheit" || input.rawUnit === "F") {
      normalizedValue = Number((((input.rawValue - 32) * 5) / 9).toFixed(2));
    } else {
      normalizedValue = Number(input.rawValue.toFixed(2));
    }
  }

  const [minVal, maxVal] = PHYSICAL_VARIABLE_LIMITS[input.variable] || [-Infinity, Infinity];
  const passedRange = normalizedValue >= minVal && normalizedValue <= maxVal;
  const qaState = passedRange ? "VALID" : "OUT_OF_RANGE";
  const qaDetails = {
    passedRange,
    passedSpike: true,
    passedFlatline: true,
    reason: passedRange ? undefined : `Normalized value ${normalizedValue} outside physical limits [${minVal}, ${maxVal}]`,
  };

  const readingId = `obs_${input.deviceId}_${input.channelId}_${Date.parse(deviceAcquiredAt)}`;

  const depthInterval =
    typeof input.nominalDepthCm === "number" && input.nominalDepthCm >= 0
      ? {
          nominalCm: input.nominalDepthCm,
          topCm: Math.max(0, input.nominalDepthCm - 5),
          bottomCm: input.nominalDepthCm + 5,
        }
      : null;

  return {
    readingId,
    deviceId: input.deviceId,
    channelId: input.channelId,
    plotId: input.plotId,
    variable: input.variable,
    rawUnit: input.rawUnit,
    normalizedUnit,
    rawValue: input.rawValue,
    normalizedValue,
    depthInterval,
    physicalPlacement: input.physicalPlacement || null,
    deviceAcquiredAt,
    serverReceivedAt,
    calibration: input.calibration || null,
    qaState,
    qaDetails,
    provenance: {
      rawPayloadRef: input.rawPayloadRef || `raw_${readingId}`,
      rawPayloadHash,
      protocol: input.protocol || "HTTP_WEBHOOK",
    },
    admissionStatus: qaState === "VALID" ? "UNADMITTED" : "REJECTED",
    admissionReason: qaState === "VALID" ? "Fresh observation awaiting Layer 0 QA qualification" : "Failed initial physical boundary QA",
  };
}

export function buildSoilDepthProfile(readings, options = {}) {
  const depths = options.standardDepths || STANDARD_SOIL_PROFILE_DEPTHS_CM;
  const vwcReadings = (readings || []).filter(
    (r) => r && r.variable === "soil_moisture_vwc" && r.depthInterval?.nominalCm != null
  );

  const plotId = options.plotId || (readings && readings[0]?.plotId) || "unknown";
  const deviceId = options.deviceId || (readings && readings[0]?.deviceId) || "unknown";
  const timestamp = options.timestamp || (readings && readings[0]?.deviceAcquiredAt) || new Date().toISOString();

  const layers = depths.map((nominalCm) => {
    const match = vwcReadings.find(
      (r) => r.depthInterval && Math.abs(r.depthInterval.nominalCm - nominalCm) <= 2.5
    );

    if (match && match.qaState === "VALID") {
      return {
        nominalCm,
        topCm: match.depthInterval?.topCm,
        bottomCm: match.depthInterval?.bottomCm,
        measured: true,
        vwcFraction: match.normalizedValue,
        reading: match,
        label: `${(match.normalizedValue * 100).toFixed(1)}%`,
      };
    }

    return {
      nominalCm,
      measured: false,
      vwcFraction: null,
      reading: null,
      label: "Not measured —",
    };
  });

  const measuredCount = layers.filter((l) => l.measured).length;
  const rootZoneAggregateAllowed = measuredCount >= 3;

  return {
    plotId,
    deviceId,
    timestamp,
    standardDepthsCm: depths,
    layers,
    measuredCount,
    rootZoneAggregateAllowed,
    supportDifferenceDisclaimer:
      "A point measurement at 15 cm and a modeled root-zone estimate represent different spatial and vertical supports. Their numerical agreement alone does not establish independent scientific validation.",
  };
}

export function checkRetroactivePublicationAdmission(reading, publication) {
  return {
    canAdmitRetroactively: false,
    reason: `Scientific boundary rejection: Observation ${reading.readingId} (acquired at ${reading.deviceAcquiredAt}, received at ${reading.serverReceivedAt}) cannot be inserted retroactively into sealed historical publication cutoff ${publication.evidence_cutoff_at}. Immutable scientific publications are sealed at publish time.`,
  };
}
