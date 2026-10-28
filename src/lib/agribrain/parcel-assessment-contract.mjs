import { createHash } from "node:crypto";

export const PARCEL_ASSESSMENT_CONTRACT_VERSION = "2026.10-p2a.1";

export function sha256Sync(ascii) {
  function rightRotate(value, amount) {
    return (value >>> amount) | (value << (32 - amount));
  }
  const mathPow = Math.pow;
  const maxWord = mathPow(2, 32);
  const lengthProperty = "length";
  let i = 0, j = 0;
  let result = "";
  const words = [];
  const unescaped = unescape(encodeURIComponent(ascii));
  const asciiBitLength = unescaped[lengthProperty] * 8;
  let hash = [];
  const k = [];
  let primeCounter = 0;
  const isComposite = {};
  for (let candidate = 2; primeCounter < 64; candidate++) {
    if (!isComposite[candidate]) {
      for (i = 0; i < 313; i += candidate) {
        isComposite[i] = true;
      }
      hash[primeCounter] = (mathPow(candidate, 0.5) * maxWord) | 0;
      k[primeCounter++] = (mathPow(candidate, 1 / 3) * maxWord) | 0;
    }
  }
  hash = hash.slice(0, 8);
  let str = unescaped + "\x80";
  while ((str[lengthProperty] % 64) - 56) str += "\x00";
  for (i = 0; i < str[lengthProperty]; i++) {
    j = str.charCodeAt(i);
    words[i >> 2] |= j << (((3 - i) % 4) * 8);
  }
  words[words[lengthProperty]] = (asciiBitLength / maxWord) | 0;
  words[words[lengthProperty]] = asciiBitLength;
  for (j = 0; j < words[lengthProperty]; ) {
    const w = words.slice(j, (j += 16));
    const oldHash = hash.slice(0);
    for (i = 0; i < 64; i++) {
      const w15 = w[i - 15], w2 = w[i - 2];
      const s0 = rightRotate(w15, 7) ^ rightRotate(w15, 18) ^ (w15 >>> 3);
      const s1 = rightRotate(w2, 17) ^ rightRotate(w2, 19) ^ (w2 >>> 10);
      w[i] = i < 16 ? w[i] : (w[i - 16] + s0 + w[i - 7] + s1) | 0;
      const ch = (hash[4] & hash[5]) ^ (~hash[4] & hash[6]);
      const maj = (hash[0] & hash[1]) ^ (hash[0] & hash[2]) ^ (hash[1] & hash[2]);
      const temp1 = (hash[7] + (rightRotate(hash[4], 6) ^ rightRotate(hash[4], 11) ^ rightRotate(hash[4], 25)) + ch + k[i] + w[i]) | 0;
      const temp2 = ((rightRotate(hash[0], 2) ^ rightRotate(hash[0], 13) ^ rightRotate(hash[0], 22)) + maj) | 0;
      hash = [(temp1 + temp2) | 0, hash[0], hash[1], hash[2], (hash[3] + temp1) | 0, hash[4], hash[5], hash[6]];
    }
    for (i = 0; i < 8; i++) {
      hash[i] = (hash[i] + oldHash[i]) | 0;
    }
  }
  for (i = 0; i < 8; i++) {
    for (let b = 3; b >= 0; b--) {
      const byte = (hash[i] >> (b * 8)) & 255;
      result += (byte < 16 ? "0" : "") + byte.toString(16);
    }
  }
  return result;
}

export function computeDeterministicHash(input) {
  try {
    return createHash("sha256").update(String(input), "utf8").digest("hex");
  } catch {
    return sha256Sync(String(input));
  }
}

export function canonicalizeGeoJson(value) {
  if (value === null || value === undefined) return value;
  if (Array.isArray(value)) return value.map(canonicalizeGeoJson);
  if (typeof value === "object") {
    return Object.fromEntries(
      Object.keys(value)
        .sort()
        .map((key) => [key, canonicalizeGeoJson(value[key])])
    );
  }
  return value;
}

export function computeGeometryHash(geometry) {
  if (!geometry) return "empty_geometry";
  let target = geometry;
  if (typeof geometry === "string") {
    try {
      target = JSON.parse(geometry);
    } catch {
      return `sha256:${computeDeterministicHash(geometry)}`;
    }
  }
  const canonicalString = JSON.stringify(canonicalizeGeoJson(target));
  return `sha256:${computeDeterministicHash(canonicalString)}`;
}

export function computeClientFingerprint(identity) {
  const canonicalPayload = [
    identity.contractVersion,
    identity.tenantId,
    identity.farmId,
    identity.plotId,
    identity.cropCycleId ?? "null",
    identity.publicationId,
    identity.runId,
    identity.snapshotId,
    identity.geometryHash,
    identity.observationWindow?.start,
    identity.observationWindow?.end,
    identity.evidenceCutoffAt,
    identity.publishedAt,
    identity.publicationReceiptHash || identity.receiptHash || "",
  ].join("|");
  return computeDeterministicHash(canonicalPayload);
}

export function computeReceiptHash(identity) {
  return computeClientFingerprint(identity);
}

export function deepFreeze(obj) {
  if (obj === null || typeof obj !== "object") return obj;
  Object.freeze(obj);
  for (const key of Object.getOwnPropertyNames(obj)) {
    const value = obj[key];
    if (value !== null && (typeof value === "object" || typeof value === "function") && !Object.isFrozen(value)) {
      deepFreeze(value);
    }
  }
  return obj;
}

function isValidIsoDate(str) {
  if (typeof str !== "string" || !str) return false;
  const d = new Date(str);
  return !isNaN(d.getTime());
}

export function validateAssessmentIdentity(identity) {
  const errors = [];
  if (!identity || typeof identity !== "object") {
    return { valid: false, errors: ["identity_must_be_non_null_object"] };
  }

  const id = identity;

  if (!id.tenantId || typeof id.tenantId !== "string" || !id.tenantId.trim()) errors.push("tenantId_required");
  if (!id.farmId || typeof id.farmId !== "string" || !id.farmId.trim()) errors.push("farmId_required");
  if (!id.plotId || typeof id.plotId !== "string" || !id.plotId.trim()) errors.push("plotId_required");
  if (!id.publicationId || typeof id.publicationId !== "string" || !id.publicationId.trim()) errors.push("publicationId_required");
  if (!id.runId || typeof id.runId !== "string" || !id.runId.trim()) errors.push("runId_required");
  if (!id.snapshotId || typeof id.snapshotId !== "string" || !id.snapshotId.trim()) errors.push("snapshotId_required");
  if (!id.geometryHash || typeof id.geometryHash !== "string" || !id.geometryHash.trim() || id.geometryHash === "empty_geometry") {
    errors.push("geometryHash_required");
  }

  if (id.contractVersion !== PARCEL_ASSESSMENT_CONTRACT_VERSION) {
    errors.push(`contractVersion_mismatch:expected_${PARCEL_ASSESSMENT_CONTRACT_VERSION}_got_${id.contractVersion}`);
  }

  if (!id.observationWindow || typeof id.observationWindow !== "object") {
    errors.push("observationWindow_required");
  } else {
    if (!isValidIsoDate(id.observationWindow.start)) errors.push("observationWindow_start_invalid");
    if (!isValidIsoDate(id.observationWindow.end)) errors.push("observationWindow_end_invalid");
    if (
      isValidIsoDate(id.observationWindow.start) &&
      isValidIsoDate(id.observationWindow.end) &&
      new Date(id.observationWindow.start).getTime() > new Date(id.observationWindow.end).getTime()
    ) {
      errors.push("observationWindow_start_after_end");
    }
  }

  if (!isValidIsoDate(id.evidenceCutoffAt)) {
    errors.push("evidenceCutoffAt_invalid");
  }
  if (!isValidIsoDate(id.publishedAt)) {
    errors.push("publishedAt_invalid");
  }

  if (isValidIsoDate(id.evidenceCutoffAt) && isValidIsoDate(id.publishedAt)) {
    if (new Date(id.publishedAt).getTime() < new Date(id.evidenceCutoffAt).getTime()) {
      errors.push("publishedAt_before_evidenceCutoffAt");
    }
  }

  const receipt = id.publicationReceiptHash || id.receiptHash;
  if (!receipt || typeof receipt !== "string") {
    errors.push("publicationReceiptHash_required");
  } else if (receipt.length < 8) {
    errors.push("publicationReceiptHash_malformed");
  }

  if (id.clientFingerprint && errors.length === 0) {
    const expectedFingerprint = computeClientFingerprint(id);
    if (id.clientFingerprint !== expectedFingerprint) {
      errors.push("clientFingerprint_mismatch");
    }
  }

  return {
    valid: errors.length === 0,
    errors,
  };
}

export function createImmutableParcelAssessment(params) {
  const validation = validateAssessmentIdentity(params.identity);
  if (!validation.valid) {
    throw new Error(`Invalid ParcelAssessmentIdentity: ${validation.errors.join("; ")}`);
  }

  const cutoffTime = new Date(params.identity.evidenceCutoffAt).getTime();
  const timeline = params.evidenceTimeline || [];

  for (const event of timeline) {
    if (event.manifestMembership === true) {
      const eventTime = new Date(event.observedAt || event.capturedAt).getTime();
      if (!isNaN(eventTime) && eventTime > cutoffTime) {
        throw new Error(
          `Observation evidence event ${event.id} (${event.observedAt || event.capturedAt}) exceeds evidenceCutoffAt (${params.identity.evidenceCutoffAt}). Late observations cannot be part of published assessment manifest.`
        );
      }
      const ingestedTime = event.ingestedAt ? new Date(event.ingestedAt).getTime() : NaN;
      if (!isNaN(ingestedTime) && ingestedTime > cutoffTime) {
        throw new Error(
          `Evidence event ${event.id} ingestion (${event.ingestedAt}) exceeds evidenceCutoffAt (${params.identity.evidenceCutoffAt}). Late-ingested evidence cannot participate in manifest.`
        );
      }
      const acceptedTime = event.acceptedAt ? new Date(event.acceptedAt).getTime() : NaN;
      if (!isNaN(acceptedTime) && acceptedTime > cutoffTime) {
        throw new Error(
          `Evidence event ${event.id} acceptance (${event.acceptedAt}) exceeds evidenceCutoffAt (${params.identity.evidenceCutoffAt}).`
        );
      }
    }
  }

  const normalizedIdentity = {
    ...params.identity,
    publicationReceiptHash: params.identity.publicationReceiptHash || params.identity.receiptHash,
    receiptHash: params.identity.receiptHash || params.identity.publicationReceiptHash,
  };

  const assessment = {
    identity: normalizedIdentity,
    canonicalLayerResults: params.canonicalLayerResults,
    authoritativeSurfaces: params.authoritativeSurfaces || [],
    topFindings: params.topFindings || [],
    quality: params.quality,
    evidenceTimeline: timeline,
  };

  return deepFreeze(assessment);
}

export function isLateArrivingEvidence(identity, evidence) {
  const cutoff = new Date(identity.evidenceCutoffAt).getTime();
  const ingested = evidence.ingestedAt ? new Date(evidence.ingestedAt).getTime() : NaN;
  const observed = new Date(evidence.observedAt || evidence.capturedAt || "").getTime();
  const accepted = evidence.acceptedAt ? new Date(evidence.acceptedAt).getTime() : NaN;

  if (!isNaN(ingested) && ingested > cutoff) return true;
  if (!isNaN(observed) && observed > cutoff) return true;
  if (!isNaN(accepted) && accepted > cutoff) return true;

  if (evidence.manifestMembership === false) return true;

  return false;
}

export function isAssessmentStaleForGeometry(identity, currentGeometry) {
  const currentHash = computeGeometryHash(currentGeometry);
  const normCurrent = currentHash.replace(/^sha256:/, "");
  const normIdentity = (identity.geometryHash || "").replace(/^sha256:/, "");
  return normCurrent !== normIdentity;
}

export function isAssessmentStaleForCropCycle(identity, currentCropCycleId) {
  return (identity.cropCycleId ?? null) !== (currentCropCycleId ?? null);
}

export function canonicalPublicationToAssessment(cacheJson, plotId, options = {}) {
  if (!cacheJson || typeof cacheJson !== "object") {
    throw new Error("Cannot construct ParcelAssessment from empty payload");
  }

  // 1. Identity normalization & verification without synthetic metadata
  const rawCutoff = cacheJson.evidence_cutoff_at ?? cacheJson.evidenceCutoffAt;
  const rawPublished = cacheJson.published_at ?? cacheJson.publishedAt;
  
  // Strict ISO strings without fallback synthesis
  const cutoffIso = rawCutoff ? new Date(rawCutoff).toISOString() : "";
  const publishedIso = rawPublished ? new Date(rawPublished).toISOString() : "";

  const observationStart = cacheJson.source_window?.[0]
    || cacheJson.observation_window?.start
    || cacheJson.observationWindow?.start
    || "";
  const observationEnd = cacheJson.source_window?.[1]
    || cacheJson.observation_window?.end
    || cacheJson.observationWindow?.end
    || "";

  const receipt = cacheJson.canonical_publication_receipt_hash
    || cacheJson.publication_receipt_hash
    || cacheJson.publicationReceiptHash
    || cacheJson.receiptHash
    || "";

  // The backend authoritative publication geometry hash must be respected.
  // Current frontend geometry is context for staleness checking, not publication rewriting.
  const geometryHash = cacheJson.geometry_hash
    || cacheJson.geometryHash
    || (options?.geometry ? computeGeometryHash(options.geometry) : "");

  const tenantId = cacheJson.tenant_id
    || cacheJson.tenantId
    || options?.tenantId
    || "";

  const farmId = cacheJson.farm_id
    || cacheJson.farmId
    || options?.farmId
    || "";

  const identity = {
    tenantId,
    farmId,
    plotId: String(plotId || cacheJson.plot_id || cacheJson.plotId || ""),
    cropCycleId: options?.cropCycleId ?? cacheJson.crop_cycle_id ?? cacheJson.cropCycleId ?? null,
    publicationId: String(cacheJson.publication_id || cacheJson.publicationId || ""),
    runId: String(cacheJson.publication_run_id || cacheJson.agribrain_run_id || cacheJson.run_id || cacheJson.runId || ""),
    snapshotId: String(cacheJson.intelligence_snapshot_id || cacheJson.snapshot_id || cacheJson.snapshotId || ""),
    geometryHash,
    observationWindow: {
      start: observationStart ? new Date(observationStart).toISOString() : "",
      end: observationEnd ? new Date(observationEnd).toISOString() : "",
    },
    evidenceCutoffAt: cutoffIso,
    publishedAt: publishedIso,
    publicationReceiptHash: receipt,
    receiptHash: receipt,
    contractVersion: PARCEL_ASSESSMENT_CONTRACT_VERSION,
  };

  const validation = validateAssessmentIdentity(identity);
  if (!validation.valid) {
    throw new Error(`Assessment identity validation failed: ${validation.errors.join("; ")}`);
  }

  // 2. Canonical Layer Results normalization (L0 - L10)
  // Confidence is number | null, missing confidence is preserved as null (never fabricated 1.0 or 0.0)
  const rawLayerResults = cacheJson.layer_results || cacheJson.layerResults || {};
  const canonicalLayerResults = {};
  for (let i = 0; i <= 10; i++) {
    const layerId = `L${i}`;
    const rawLayer = rawLayerResults[layerId] || rawLayerResults[String(i)] || null;
    if (rawLayer) {
      const statusRaw = String(rawLayer.status || "UNAVAILABLE").toUpperCase();
      const status =
        statusRaw === "OK" || statusRaw === "COMPLETED" ? "OK"
        : statusRaw === "DEGRADED" ? "DEGRADED"
        : statusRaw === "FAILED" ? "FAILED"
        : statusRaw === "SKIPPED" ? "SKIPPED"
        : "UNAVAILABLE";
      canonicalLayerResults[layerId] = {
        layerId,
        status,
        confidence: typeof rawLayer.confidence === "number" && Number.isFinite(rawLayer.confidence)
          ? Math.max(0, Math.min(1, rawLayer.confidence))
          : null,
        sources: Array.isArray(rawLayer.sources) ? rawLayer.sources : [],
        summary: rawLayer.summary || undefined,
        flags: Array.isArray(rawLayer.flags) ? rawLayer.flags : Array.isArray(rawLayer.degradation_flags) ? rawLayer.degradation_flags : undefined,
        data: typeof rawLayer.data === "object" && rawLayer.data !== null ? rawLayer.data : undefined,
      };
    } else {
      canonicalLayerResults[layerId] = {
        layerId,
        status: "UNAVAILABLE",
        confidence: null,
        sources: [],
      };
    }
  }

  // 3. Authoritative Surfaces
  const authoritativeSurfaces = Array.isArray(cacheJson.surfaceGrids)
    ? cacheJson.surfaceGrids
    : Array.isArray(cacheJson.surfaces)
    ? cacheJson.surfaces
    : [];

  // 4. Top Findings normalization
  // Heuristic regex keyword severity is prohibited. Strings are unclassified info with actionable=false.
  const rawTopFindings = Array.isArray(cacheJson.top_findings)
    ? cacheJson.top_findings
    : Array.isArray(cacheJson.topFindings)
    ? cacheJson.topFindings
    : [];
  const topFindings = rawTopFindings.map((item, idx) => {
    if (typeof item === "string") {
      return {
        id: `finding-${idx + 1}`,
        title: item,
        severity: "info",
        description: item,
        actionable: false,
      };
    }
    return {
      id: String(item.id || `finding-${idx + 1}`),
      title: String(item.title || item.headline || "Finding"),
      severity: item.severity || "info",
      description: String(item.description || item.detail || item.title || ""),
      layerId: item.layerId || item.layer_id || undefined,
      actionable: Boolean(item.actionable),
      evidenceSources: Array.isArray(item.evidenceSources) ? item.evidenceSources : undefined,
    };
  });

  // 5. Assessment Quality
  // Missing degradationMode is UNKNOWN, never defaulted to NORMAL
  const rawQuality = cacheJson.quality || {};
  const rawGlobalQuality = cacheJson.global_quality || {};
  const quality = {
    degradationMode: String(rawQuality.degradation_mode || rawGlobalQuality.degradation_mode || "UNKNOWN"),
    reliabilityScore: typeof rawQuality.reliability_score === "number"
      ? rawQuality.reliability_score
      : typeof rawGlobalQuality.reliability_score === "number"
      ? rawGlobalQuality.reliability_score
      : null,
    warnings: Array.isArray(rawQuality.warnings) ? rawQuality.warnings : [],
    criticalErrors: Array.isArray(rawQuality.criticalErrors) ? rawQuality.criticalErrors : undefined,
    surfacesGenerated: Number(rawQuality.surfaces_generated ?? authoritativeSurfaces.length),
    zonesGenerated: Number(rawQuality.zones_generated ?? (Array.isArray(cacheJson.zones) ? cacheJson.zones.length : 0)),
    gridAlignmentOk: typeof rawQuality.grid_alignment_ok === "boolean"
      ? rawQuality.grid_alignment_ok
      : null,
    detailConservationOk: typeof rawQuality.detail_conservation_ok === "boolean"
      ? rawQuality.detail_conservation_ok
      : null,
  };

  // 6. Evidence Timeline
  // Manifest membership and verification are NOT invented: unknown remains false.
  const rawTimeline = Array.isArray(cacheJson.timeline)
    ? cacheJson.timeline
    : Array.isArray(cacheJson.evidence_timeline)
    ? cacheJson.evidence_timeline
    : [];
  const evidenceTimeline = rawTimeline.map((item, idx) => {
    const observedAt = String(item.observedAt || item.observed_at || item.capturedAt || item.timestamp || "");
    return {
      id: String(item.id || `evidence-${idx + 1}`),
      type: item.type || "observation",
      source: String(item.source || "unknown"),
      observedAt,
      capturedAt: observedAt,
      ingestedAt: item.ingestedAt || item.ingested_at || null,
      acceptedAt: item.acceptedAt || item.accepted_at || null,
      manifestMembership: item.manifestMembership !== undefined ? Boolean(item.manifestMembership) : false,
      summary: String(item.summary || item.description || "Evidence observation"),
      verified: item.verified !== undefined ? Boolean(item.verified) : false,
    };
  });

  return createImmutableParcelAssessment({
    identity,
    canonicalLayerResults,
    authoritativeSurfaces,
    topFindings,
    quality,
    evidenceTimeline,
  });
}
