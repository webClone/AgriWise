import { createHash } from "node:crypto";

export const CROP_RUNTIME_DECLARATION_VERSION =
  "crop_runtime_declaration_v1";

const AUTHORITIES = new Set([
  "FARMER_CONFIRMED",
  "AGRONOMIST_CONFIRMED",
  "OFFICIAL_PARCEL_LABEL",
]);

function requiredText(value, name) {
  const normalized = String(value ?? "").trim();
  if (!normalized) throw new Error(`${name} is required`);
  return normalized;
}

function normalizeCrop(value) {
  return requiredText(value, "crop_code")
    .toLowerCase()
    .replace(/[- ]/g, "_");
}

function freezeDeep(value) {
  if (!value || typeof value !== "object" || Object.isFrozen(value)) {
    return value;
  }
  for (const child of Object.values(value)) freezeDeep(child);
  return Object.freeze(value);
}

function canonicalize(value) {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.keys(value).sort().map((key) => [key, canonicalize(value[key])]),
    );
  }
  if (typeof value === "number" && !Number.isFinite(value)) {
    throw new Error("runtime crop declaration contains a non-finite number");
  }
  return value;
}

function declarationContentHash(payload) {
  return createHash("sha256")
    .update(JSON.stringify(canonicalize(payload)), "utf8")
    .digest("hex");
}

/**
 * Validate the server receipt before the UI reports that a declaration will
 * affect the next scientific run. This receipt identifies runtime CropCycle
 * state; it is deliberately distinct from an audit/training label id.
 */
export function normalizeCropRuntimeDeclarationReceipt(value, expected) {
  if (!value || typeof value !== "object") {
    throw new Error("runtime crop declaration receipt is required");
  }
  if (value.contract_version !== CROP_RUNTIME_DECLARATION_VERSION) {
    throw new Error("unsupported runtime crop declaration contract");
  }
  const namespace = value.plot_namespace ?? {};
  const resultNamespace = {
    tenant_id: requiredText(namespace.tenant_id, "plot_namespace.tenant_id"),
    farm_id: requiredText(namespace.farm_id, "plot_namespace.farm_id"),
    plot_id: requiredText(namespace.plot_id, "plot_namespace.plot_id"),
  };
  if (expected && ["tenant_id", "farm_id", "plot_id"].some(
    (key) => expected[key] && String(expected[key]) !== resultNamespace[key],
  )) {
    throw new Error("runtime crop declaration namespace mismatch");
  }
  const authority = requiredText(value.authority, "authority").toUpperCase();
  if (!AUTHORITIES.has(authority)) {
    throw new Error("unsupported runtime crop declaration authority");
  }
  const declaredAt = new Date(requiredText(value.declared_at, "declared_at"));
  if (Number.isNaN(declaredAt.getTime())) {
    throw new Error("runtime crop declaration declared_at is invalid");
  }
  if (value.plant_date_asserted !== false) {
    throw new Error("crop identity declaration cannot assert a planting date");
  }
  if (typeof value.cycle_created !== "boolean") {
    throw new Error("runtime crop declaration cycle_created must be boolean");
  }
  const contentHash = requiredText(value.content_hash, "content_hash");
  if (!/^[0-9a-f]{64}$/.test(contentHash)) {
    throw new Error("runtime crop declaration content_hash is invalid");
  }
  const payload = {
    contract_version: value.contract_version,
    plot_namespace: resultNamespace,
    crop_cycle_id: requiredText(value.crop_cycle_id, "crop_cycle_id"),
    crop_code: normalizeCrop(value.crop_code),
    authority,
    declared_at: declaredAt.toISOString(),
    source: requiredText(value.source, "source"),
    cycle_created: value.cycle_created,
    plant_date_asserted: false,
  };
  if (declarationContentHash(payload) !== contentHash) {
    throw new Error("runtime crop declaration content_hash mismatch");
  }
  return freezeDeep({
    ...payload,
    content_hash: contentHash,
  });
}
