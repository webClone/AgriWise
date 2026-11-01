/**
 * Operational telemetry transport adapter.
 * SensorReading.timestamp is currently server receipt/write time, not device
 * acquisition time. PlotObservation.obsDate may instead be a legacy daily
 * grouping bucket; only matching data.observed_at qualifies its precise
 * acquisition time. fetchedAt is the ingestion time. None certifies evidence.
 *
 * This module does not read or mutate ParcelAssessment or publish evidence.
 */
export const OPERATIONAL_TELEMETRY_METRICS = Object.freeze([
  ["temperature", "temp", "°C"],
  ["humidity", "humidity", "%"],
  ["rainfall", "rain", "mm"],
  ["soilMoisture", "soilMoisture", "%"],
  ["et0", "et0", "mm/day"],
]);

const iso = value => {
  if (value instanceof Date) return Number.isFinite(value.getTime()) ? value.toISOString() : null;
  if (typeof value === "string" && /^\d{4}-\d\d-\d\dT/.test(value)) {
    const time = Date.parse(value);
    return Number.isFinite(time) ? new Date(time).toISOString() : null;
  }
  return null;
};
const finite = value => typeof value === "number" && Number.isFinite(value);

// Existing daily aggregates and current-weather rows without a provider
// acquisition clock must never be misrepresented as exact observations.
// The full provider clock is stored inside PlotObservation.data.observed_at.
function plotObservationClock(row) {
  const bucketClock = iso(row.obsDate);
  const providerClock = iso(row.data?.observed_at);
  const qualified = (row.obsType === "current_weather" || row.obsType === "sensor_reading")
    && !!bucketClock && !!providerClock
    && Math.abs(Date.parse(bucketClock) - Date.parse(providerClock)) < 1000;
  return {
    observedAt: qualified ? providerClock : bucketClock,
    timeBasis: qualified ? "source_observation_at" : "day_bucket_unverified",
    dayBucketDate: bucketClock?.slice(0, 10),
  };
}

function emitRows(rows, scope, spec) {
  const out = [];
  for (const row of rows || []) {
    if (!row?.id) continue;
    const provenance = spec.clockResolver ? spec.clockResolver(row) : {
      observedAt: iso(row[spec.observed]),
      timeBasis: spec.timeBasis,
      dayBucketDate: iso(row[spec.observed])?.slice(0, 10),
    };
    const observedAt = provenance.observedAt;
    const ingestedAt = iso(row[spec.ingested]);
    if (!observedAt || !ingestedAt) continue;
    const obsType = typeof row.obsType === "string" ? row.obsType : (spec.defaultObsType || undefined);
    if (obsType && /forecast/i.test(obsType)) continue;
    for (const [field, metric, unit] of spec.fields) {
      if (!finite(row[field])) continue;
      out.push({
        id: spec.prefix + ":" + String(row.id) + ":" + metric,
        scope: { ...scope },
        source: spec.source(row),
        kind: "observation",
        observedAt,
        ingestedAt,
        timeBasis: provenance.timeBasis,
        ...(provenance.dayBucketDate ? { dayBucketDate: provenance.dayBucketDate } : {}),
        metric, value: row[field], unit,
        ...(obsType ? { obsType } : {}),
      });
    }
  }
  return out;
}

/**
 * Read-only projection of already-persisted measurements. Returned records
 * are never described as verified/admitted or as canonical scientific results.
 */
export function serializeOperationalTelemetry({ sensorReadings = [], plotObservations = [], scope }) {
  if (!scope?.tenantId || !scope?.farmId || !scope?.plotId) {
    throw new Error("telemetry_scope_incomplete");
  }
  const sensor = emitRows(sensorReadings, scope, {
    observed: "timestamp", ingested: "timestamp",
    prefix: "sensor-reading", timeBasis: "server_received_at", defaultObsType: "sensor_reading",
    source: row => "sensor:" + String(row.sensor?.deviceId || row.sensorId || "unknown"),
    fields: [
      ["temperature", "temp", "°C"], ["humidity", "humidity", "%"],
      ["rainfall", "rain", "mm"], ["soilMoisture", "soilMoisture", "%"],
    ],
  });
  const persisted = emitRows(plotObservations, scope, {
    observed: "obsDate", ingested: "fetchedAt",
    prefix: "plot-observation", clockResolver: plotObservationClock,
    defaultObsType: "plot_observation",
    source: row => "plot-source:" + String(row.source || "unknown"),
    fields: [
      ["tempC", "temp", "°C"], ["humidity", "humidity", "%"],
      ["precipMm", "rain", "mm"], ["soilMoisture", "soilMoisture", "%"],
      ["et0", "et0", "mm/day"],
    ],
  });
  // Both source tables may describe the same measurement; source-specific
  // identities are stable and intentionally not merged without a shared ID.
  return [...sensor, ...persisted];
}

export function validateOperationalTelemetryResponse(body, scope, version) {
  if (!body || body.contractVersion !== version
    || !body.scope || body.scope.tenantId !== scope.tenantId
    || body.scope.farmId !== scope.farmId || body.scope.plotId !== scope.plotId
    || !Array.isArray(body.observations) || body.observations.length > 500) {
    throw new Error("telemetry_response_scope_or_contract_invalid");
  }
  for (const row of body.observations) {
    if (!row || row.kind !== "observation" || typeof row.id !== "string" || !row.id
      || typeof row.source !== "string" || !row.source
      || !iso(row.observedAt) || !iso(row.ingestedAt)
      || !["temp", "rain", "humidity", "soilMoisture", "et0"].includes(row.metric)
      || !finite(row.value) || typeof row.unit !== "string"
      || !["server_received_at", "source_observation_at", "day_bucket_unverified"].includes(row.timeBasis)
      || (row.dayBucketDate !== undefined && (typeof row.dayBucketDate !== "string" || !/^\d{4}-\d\d-\d\d$/.test(row.dayBucketDate)))
      || (row.obsType !== undefined && (typeof row.obsType !== "string" || !row.obsType || /forecast/i.test(row.obsType)))
      || !row.scope || row.scope.tenantId !== scope.tenantId
      || row.scope.farmId !== scope.farmId || row.scope.plotId !== scope.plotId
      || row.certified === true || row.manifestMembership === true
      || row.certificationStatus === "CERTIFIED_MANIFEST") {
      throw new Error("telemetry_response_observation_invalid");
    }
  }
  return body.observations;
}
