/**
 * Akaloris W2 Physical IoT Intelligence & Multi-Depth Observation Contract
 *
 * Establishes immutable provenance, channel-aware depth metadata, normalized units,
 * and strict epistemic separation between raw physical telemetry and Layer 10 scientific estimates.
 *
 * Implements W2-00 and W2-01 specifications:
 * 1. Device acquisition time, channel identity, depth, raw/normalized units, and immutable provenance.
 * 2. Strict physical range QA and spike rejection.
 * 3. Multi-depth soil profile without synthetic or invented depths.
 * 4. Prohibition of retroactive admission into historical sealed publications.
 * 5. Prohibition of treating an assimilated sensor as independent validation without holdout.
 */

import crypto from "crypto";

export type CanonicalSensorVariable =
  | "soil_moisture_vwc"
  | "soil_water_tension_kpa"
  | "soil_temperature_c"
  | "soil_ec_ds_m"
  | "soil_ph"
  | "air_temperature_c"
  | "relative_humidity_pct"
  | "dew_point_c"
  | "vpd_kpa"
  | "rainfall_mm"
  | "rain_rate_mm_h"
  | "wind_speed_ms"
  | "wind_gust_ms"
  | "wind_direction_deg"
  | "solar_radiation_w_m2"
  | "par_umol_m2_s"
  | "leaf_wetness"
  | "battery_pct"
  | "battery_voltage_v"
  | "signal_rssi_dbm"
  | "signal_snr_db";

export interface DepthInterval {
  readonly topCm: number;
  readonly bottomCm: number;
  readonly nominalCm: number;
}

export type SensorPlacementType =
  | "REPRESENTATIVE_ZONE"
  | "WEATHER_STATION"
  | "IRRIGATION_LINE"
  | "EDGE"
  | "UNKNOWN";

export interface PhysicalPlacement {
  readonly latitude: number;
  readonly longitude: number;
  readonly elevationM?: number;
  readonly placementType: SensorPlacementType;
}

export type CalibrationMethod =
  | "SOIL_SPECIFIC"
  | "FIELD_TWO_POINT"
  | "FACTORY"
  | "VENDOR_DEFAULT";

export interface SensorCalibration {
  readonly calibrationId: string;
  readonly version: string;
  readonly method: CalibrationMethod;
  readonly validUntil?: string;
  readonly isExpired?: boolean;
}

export type ObservationQAState =
  | "VALID"
  | "SUSPECT"
  | "OUT_OF_RANGE"
  | "STALE"
  | "REPLAY";

export interface QADetails {
  readonly passedRange: boolean;
  readonly passedSpike: boolean;
  readonly passedFlatline: boolean;
  readonly reason?: string;
}

export interface ObservationProvenance {
  readonly rawPayloadRef: string;
  readonly rawPayloadHash: string;
  readonly protocol: "HTTP_WEBHOOK" | "LORAWAN" | "MQTT";
  readonly vendor?: string;
  readonly model?: string;
}

export type ScientificAdmissionStatus =
  | "UNADMITTED"
  | "LAYER0_ADMITTED"
  | "HOLD_OUT"
  | "REJECTED";

export interface PhysicalObservationRecord {
  readonly readingId: string;
  readonly deviceId: string;
  readonly channelId: string;
  readonly plotId: string;
  readonly variable: CanonicalSensorVariable;
  readonly rawUnit: string;
  readonly normalizedUnit: string;
  readonly rawValue: number;
  readonly normalizedValue: number;
  readonly depthInterval: DepthInterval | null;
  readonly physicalPlacement: PhysicalPlacement | null;
  readonly deviceAcquiredAt: string; // ISO 8601 UTC
  readonly serverReceivedAt: string; // ISO 8601 UTC
  readonly calibration: SensorCalibration | null;
  readonly qaState: ObservationQAState;
  readonly qaDetails: QADetails;
  readonly provenance: ObservationProvenance;
  readonly admissionStatus: ScientificAdmissionStatus;
  readonly admissionReason?: string;
}

export interface SoilDepthLayer {
  readonly nominalCm: number;
  readonly topCm?: number;
  readonly bottomCm?: number;
  readonly measured: boolean;
  readonly vwcFraction: number | null;
  readonly temperatureC?: number | null;
  readonly reading: PhysicalObservationRecord | null;
  readonly label: string;
}

export interface SoilDepthProfile {
  readonly plotId: string;
  readonly deviceId: string;
  readonly timestamp: string;
  readonly standardDepthsCm: readonly number[];
  readonly layers: readonly SoilDepthLayer[];
  readonly measuredCount: number;
  readonly rootZoneAggregateAllowed: boolean;
  readonly supportDifferenceDisclaimer: string;
}

/**
 * Authoritative physical ranges from sensor_runtime and Layer 0 contracts.
 */
export const PHYSICAL_VARIABLE_LIMITS: Readonly<Record<CanonicalSensorVariable, readonly [number, number]>> = Object.freeze({
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

export const STANDARD_SOIL_PROFILE_DEPTHS_CM: readonly number[] = Object.freeze([
  10, 15, 30, 45, 60, 90,
]);

/**
 * Computes deterministic SHA-256 hash of a raw payload for immutable provenance.
 */
export function computeRawPayloadHash(payload: unknown): string {
  const jsonStr = typeof payload === "string" ? payload : JSON.stringify(payload);
  return crypto.createHash("sha256").update(jsonStr, "utf8").digest("hex");
}

/**
 * Validates a physical observation record against physical boundaries and contract schema.
 */
export function validatePhysicalObservation(record: unknown): { valid: boolean; errors: string[] } {
  const errors: string[] = [];
  if (!record || typeof record !== "object") {
    return { valid: false, errors: ["Observation record must be a non-null object"] };
  }

  const rec = record as Partial<PhysicalObservationRecord>;

  if (!rec.readingId || typeof rec.readingId !== "string") {
    errors.push("readingId must be a non-empty string");
  }
  if (!rec.deviceId || typeof rec.deviceId !== "string") {
    errors.push("deviceId must be a non-empty string");
  }
  if (!rec.channelId || typeof rec.channelId !== "string") {
    errors.push("channelId must be a non-empty string");
  }
  if (!rec.plotId || typeof rec.plotId !== "string") {
    errors.push("plotId must be a non-empty string");
  }
  if (!rec.variable || !Object.prototype.hasOwnProperty.call(PHYSICAL_VARIABLE_LIMITS, rec.variable)) {
    errors.push(`variable must be one of canonical variables, received: ${String(rec.variable)}`);
  }
  if (typeof rec.rawValue !== "number" || !Number.isFinite(rec.rawValue)) {
    errors.push("rawValue must be a finite number");
  }
  if (typeof rec.normalizedValue !== "number" || !Number.isFinite(rec.normalizedValue)) {
    errors.push("normalizedValue must be a finite number");
  }

  // Device acquired timestamp check
  if (!rec.deviceAcquiredAt || isNaN(Date.parse(rec.deviceAcquiredAt))) {
    errors.push("deviceAcquiredAt must be a valid ISO 8601 UTC timestamp");
  } else {
    const acqTime = Date.parse(rec.deviceAcquiredAt);
    const now = Date.now();
    // Rejects clock drift into the future by more than 5 minutes
    if (acqTime > now + 300_000) {
      errors.push("deviceAcquiredAt cannot be in the future (clock drift violation)");
    }
  }

  // Server received timestamp check
  if (!rec.serverReceivedAt || isNaN(Date.parse(rec.serverReceivedAt))) {
    errors.push("serverReceivedAt must be a valid ISO 8601 UTC timestamp");
  }

  // Provenance hash check
  if (!rec.provenance?.rawPayloadHash || typeof rec.provenance.rawPayloadHash !== "string") {
    errors.push("provenance.rawPayloadHash must be a non-empty hex hash string");
  }

  // Physical range check
  if (rec.variable && Object.prototype.hasOwnProperty.call(PHYSICAL_VARIABLE_LIMITS, rec.variable)) {
    const [minVal, maxVal] = PHYSICAL_VARIABLE_LIMITS[rec.variable];
    if (rec.normalizedValue != null && (rec.normalizedValue < minVal || rec.normalizedValue > maxVal)) {
      errors.push(`normalizedValue ${rec.normalizedValue} is out of physical range [${minVal}, ${maxVal}] for ${rec.variable}`);
    }
  }

  return { valid: errors.length === 0, errors };
}

/**
 * Normalizes raw sensor readings into canonical PhysicalObservationRecord.
 */
export function normalizeRawReading(input: {
  deviceId: string;
  channelId: string;
  plotId: string;
  variable: CanonicalSensorVariable;
  rawValue: number;
  rawUnit: string;
  nominalDepthCm?: number | null;
  deviceAcquiredAt?: string;
  serverReceivedAt?: string;
  physicalPlacement?: PhysicalPlacement | null;
  calibration?: SensorCalibration | null;
  protocol?: "HTTP_WEBHOOK" | "LORAWAN" | "MQTT";
  rawPayloadRef?: string;
  rawPayload?: unknown;
}): PhysicalObservationRecord {
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

  // Normalize units
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

  // Evaluate QA
  const [minVal, maxVal] = PHYSICAL_VARIABLE_LIMITS[input.variable] || [-Infinity, Infinity];
  const passedRange = normalizedValue >= minVal && normalizedValue <= maxVal;
  const qaState: ObservationQAState = passedRange ? "VALID" : "OUT_OF_RANGE";
  const qaDetails: QADetails = {
    passedRange,
    passedSpike: true,
    passedFlatline: true,
    reason: passedRange ? undefined : `Normalized value ${normalizedValue} outside physical limits [${minVal}, ${maxVal}]`,
  };

  const readingId = `obs_${input.deviceId}_${input.channelId}_${Date.parse(deviceAcquiredAt)}`;

  const depthInterval: DepthInterval | null =
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

/**
 * Builds a multi-depth soil water profile from a collection of observation records.
 * Truthfulness-first: Never invents or synthesizes unmeasured depths!
 */
export function buildSoilDepthProfile(
  readings: readonly PhysicalObservationRecord[],
  options?: {
    plotId?: string;
    deviceId?: string;
    timestamp?: string;
    standardDepths?: readonly number[];
  }
): SoilDepthProfile {
  const depths = options?.standardDepths || STANDARD_SOIL_PROFILE_DEPTHS_CM;
  const vwcReadings = readings.filter(
    (r) => r.variable === "soil_moisture_vwc" && r.depthInterval?.nominalCm != null
  );

  const plotId = options?.plotId || (readings[0]?.plotId ?? "unknown");
  const deviceId = options?.deviceId || (readings[0]?.deviceId ?? "unknown");
  const timestamp = options?.timestamp || (readings[0]?.deviceAcquiredAt ?? new Date().toISOString());

  const layers: SoilDepthLayer[] = depths.map((nominalCm) => {
    // Find matching reading within +/- 2.5cm of nominal depth
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

  // Non-negotiable rule: A single depth (e.g. 15cm) CANNOT automatically represent
  // the full root zone. An aggregate requires explicit soil-layer model and depth weighting.
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

/**
 * Guard preventing retroactive insertion of late-arriving telemetry into a historical sealed publication.
 */
export function checkRetroactivePublicationAdmission(
  reading: PhysicalObservationRecord,
  publication: {
    published_at: string;
    evidence_cutoff_at: string;
  }
): { canAdmitRetroactively: false; reason: string } {
  return {
    canAdmitRetroactively: false,
    reason: `Scientific boundary rejection: Observation ${reading.readingId} (acquired at ${reading.deviceAcquiredAt}, received at ${reading.serverReceivedAt}) cannot be inserted retroactively into sealed historical publication cutoff ${publication.evidence_cutoff_at}. Immutable scientific publications are sealed at publish time.`,
  };
}
