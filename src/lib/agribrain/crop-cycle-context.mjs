import * as crypto from "node:crypto";

export const CROP_CYCLE_CONTEXT_CONTRACT_VERSION =
  "canonical_crop_cycle_context_v2";

const ADMINISTRATIVE_STATUS_ROLE =
  "workflow_only_not_phenology_evidence";
const DECLARATION_AUTHORITIES = new Set([
  "UNKNOWN",
  "REGISTRY_DECLARED",
  "USER_CONFIRMED",
  "FARMER_CONFIRMED",
  "OFFICIAL_PARCEL_LABEL",
  "AGRONOMIST_CONFIRMED",
]);
const PLANT_DATE_STATUSES = new Set([
  "confirmed",
  "estimated",
  "interval",
  "unknown",
]);

function canonicalize(value) {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.keys(value)
        .sort()
        .map((key) => [key, canonicalize(value[key])]),
    );
  }
  return value;
}

export function canonicalScientificHash(value) {
  return crypto
    .createHash("sha256")
    .update(JSON.stringify(canonicalize(value)), "utf8")
    .digest("hex");
}

function deepFreeze(value) {
  if (!value || typeof value !== "object" || Object.isFrozen(value)) {
    return value;
  }
  for (const child of Object.values(value)) deepFreeze(child);
  return Object.freeze(value);
}

function requiredText(value, name) {
  const result = String(value ?? "").trim();
  if (!result) throw new Error(`${name} is required`);
  return result;
}

function optionalText(value) {
  const result = String(value ?? "").trim();
  return result || null;
}

function normalizeCrop(value) {
  return (
    String(value ?? "unknown")
      .trim()
      .toLowerCase()
      .replace(/[- ]/g, "_") || "unknown"
  );
}

function normalizeDate(value) {
  if (value === null || value === undefined || value === "") return null;
  const parsed = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    throw new Error(`Invalid crop-cycle date: ${String(value)}`);
  }
  return parsed.toISOString();
}

export function buildCanonicalCropCycleContextV2(input) {
  if (!input || typeof input !== "object") {
    throw new Error("crop cycle context input is required");
  }
  if (
    Object.hasOwn(input, "stage") ||
    Object.hasOwn(input, "crop_stage") ||
    Object.hasOwn(input, "phenology_stage")
  ) {
    throw new Error("administrative status cannot be coerced into phenology");
  }

  const rawNamespace = input.plot_namespace ?? input.plotNamespace ?? {};
  const plotNamespace = {
    tenant_id: requiredText(
      rawNamespace.tenant_id ?? rawNamespace.tenantId,
      "plot_namespace.tenant_id",
    ),
    farm_id: requiredText(
      rawNamespace.farm_id ?? rawNamespace.farmId,
      "plot_namespace.farm_id",
    ),
    plot_id: requiredText(
      rawNamespace.plot_id ?? rawNamespace.plotId,
      "plot_namespace.plot_id",
    ),
  };
  const authority = String(
    input.declared_crop_authority ?? input.declaredCropAuthority ?? "UNKNOWN",
  )
    .trim()
    .toUpperCase() || "UNKNOWN";
  if (!DECLARATION_AUTHORITIES.has(authority)) {
    throw new Error(`Unsupported declared_crop_authority: ${authority}`);
  }

  const rawPlantInput = input.plant_date ?? input.plantDate ?? null;
  const rawPlantDate =
    rawPlantInput &&
    typeof rawPlantInput === "object" &&
    !(rawPlantInput instanceof Date)
      ? rawPlantInput
      : {};
  const scalarPlantDate =
    rawPlantInput instanceof Date ||
    (rawPlantInput !== null && typeof rawPlantInput !== "object")
      ? rawPlantInput
      : null;
  const plantingDateAlias = input.planting_date ?? input.plantingDate ?? null;
  if (
    scalarPlantDate !== null &&
    plantingDateAlias !== null &&
    normalizeDate(scalarPlantDate) !== normalizeDate(plantingDateAlias)
  ) {
    throw new Error("plant_date and planting_date aliases disagree");
  }
  const nominal = normalizeDate(
    rawPlantDate.nominal ??
      scalarPlantDate ??
      plantingDateAlias,
  );
  let rangeStart = normalizeDate(
    input.plant_date_min ??
      input.plantDateMin ??
      rawPlantDate.range_start ??
      rawPlantDate.rangeStart,
  );
  let rangeEnd = normalizeDate(
    input.plant_date_max ??
      input.plantDateMax ??
      rawPlantDate.range_end ??
      rawPlantDate.rangeEnd,
  );
  if (rangeStart && rangeEnd && rangeStart > rangeEnd) {
    throw new Error("plant_date.range_start must not exceed range_end");
  }
  if (nominal) {
    rangeStart ||= nominal;
    rangeEnd ||= nominal;
  }
  const plantDateStatus = String(
    input.plant_date_status ??
      input.plantDateStatus ??
      rawPlantDate.status ??
      "unknown",
  ).trim().toLowerCase() || "unknown";
  if (!PLANT_DATE_STATUSES.has(plantDateStatus)) {
    throw new Error(`Unsupported plant_date_status: ${plantDateStatus}`);
  }
  if (["confirmed", "estimated"].includes(plantDateStatus) && !nominal) {
    throw new Error(`plant_date is required for ${plantDateStatus} status`);
  }
  if (plantDateStatus === "interval" && !(rangeStart && rangeEnd)) {
    throw new Error(
      "plant_date_min and plant_date_max are required for interval status",
    );
  }
  if (plantDateStatus === "unknown" && (nominal || rangeStart || rangeEnd)) {
    throw new Error("unknown plant_date_status cannot carry dates");
  }
  let confidence =
    input.plant_date_confidence ??
    input.plantDateConfidence ??
    rawPlantDate.confidence ??
    null;
  if (confidence !== null) {
    confidence = Number(confidence);
    if (!Number.isFinite(confidence) || confidence < 0 || confidence > 1) {
      throw new Error("plant_date.confidence must be within [0, 1]");
    }
  }

  const rawHarvest = input.harvest_dates ?? input.harvestDates ?? {};
  const rawRefs = input.management_event_refs ?? input.managementEventRefs ?? [];
  if (!Array.isArray(rawRefs)) {
    throw new Error("management_event_refs must be an array");
  }
  const refs = [...rawRefs]
    .map((value) => String(value ?? "").trim())
    .filter(Boolean);

  const payload = {
    contract_version: CROP_CYCLE_CONTEXT_CONTRACT_VERSION,
    plot_namespace: plotNamespace,
    crop_cycle_id: requiredText(
      input.crop_cycle_id ?? input.cropCycleId,
      "crop_cycle_id",
    ),
    geometry_version: requiredText(
      input.geometry_version ?? input.geometryVersion,
      "geometry_version",
    ),
    effective_at: normalizeDate(
      requiredText(input.effective_at ?? input.effectiveAt, "effective_at"),
    ),
    declared_crop_code: normalizeCrop(
      input.declared_crop_code ?? input.declaredCropCode,
    ),
    declared_crop_authority: authority,
    declared_crop_at: normalizeDate(
      input.declared_crop_at ?? input.declaredCropAt ?? null,
    ),
    declared_crop_source:
      String(
        input.declared_crop_source ?? input.declaredCropSource ?? "unknown",
      ).trim().toLowerCase() || "unknown",
    variety: optionalText(input.variety),
    irrigation_type:
      String(input.irrigation_type ?? input.irrigationType ?? "unknown")
        .trim()
        .toLowerCase() || "unknown",
    // Layer 2 reads these explicit names. `planting_date` is a hash-bound
    // compatibility alias and can never diverge from `plant_date`.
    plant_date: nominal,
    planting_date: nominal,
    plant_date_status: plantDateStatus,
    plant_date_source:
      String(
        input.plant_date_source ??
          input.plantDateSource ??
          rawPlantDate.source ??
          "unknown",
      ).trim().toLowerCase() || "unknown",
    plant_date_confidence: confidence,
    plant_date_min: rangeStart,
    plant_date_max: rangeEnd,
    harvest_dates: {
      expected: normalizeDate(rawHarvest.expected),
      actual: normalizeDate(rawHarvest.actual),
    },
    administrative_status: String(
      input.administrative_status ?? input.administrativeStatus ?? "UNKNOWN",
    )
      .trim()
      .toUpperCase() || "UNKNOWN",
    administrative_status_role: ADMINISTRATIVE_STATUS_ROLE,
    management_event_refs: [...new Set(refs)].sort(),
    phenology_from_administrative_status_allowed: false,
  };
  const result = {
    ...payload,
    content_hash: canonicalScientificHash(payload),
  };
  return deepFreeze(result);
}
