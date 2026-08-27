import * as crypto from "crypto";

/**
 * RFC 3986 percent-encoding helper.
 * Unreserved characters: A-Z a-z 0-9 - _ . ~
 * Spaces become %20 (NOT +).
 */
export function rfc3986Encode(str) {
  return encodeURIComponent(String(str ?? "")).replace(
    /[!'()*]/g,
    (c) => `%${c.charCodeAt(0).toString(16).toUpperCase()}`
  );
}

/**
 * Canonicalizes query parameter key-value pairs.
 * Input: Array of [key, value] pairs or Record<string, string | string[]>
 * Sorts pairs lexicographically by key, then by value.
 * Produces key1=val1&key2=val2
 */
export function canonicalizeQueryParams(params) {
  let pairs = [];
  if (Array.isArray(params)) {
    pairs = params.map(([k, v]) => [String(k), String(v ?? "")]);
  } else if (params && typeof params === "object") {
    for (const [key, val] of Object.entries(params)) {
      if (Array.isArray(val)) {
        for (const item of val) {
          pairs.push([String(key), String(item ?? "")]);
        }
      } else if (val !== undefined && val !== null) {
        pairs.push([String(key), String(val)]);
      }
    }
  }

  pairs.sort((a, b) => {
    if (a[0] < b[0]) return -1;
    if (a[0] > b[0]) return 1;
    if (a[1] < b[1]) return -1;
    if (a[1] > b[1]) return 1;
    return 0;
  });

  return pairs
    .map(([k, v]) => `${rfc3986Encode(k)}=${rfc3986Encode(v)}`)
    .join("&");
}

export function buildCanonicalString({
  method,
  pathname,
  queryString = "",
  tenantId,
  farmId,
  plotId,
  bodyText = "",
  timestamp,
  nonce,
  keyVersion = "v1",
}) {
  const bodyHash = crypto.createHash("sha256").update(bodyText, "utf8").digest("hex");
  const canonicalQuery =
    typeof queryString === "string"
      ? queryString.trim()
      : canonicalizeQueryParams(queryString);

  return [
    String(method).toUpperCase().trim(),
    String(pathname).trim(),
    canonicalQuery,
    String(tenantId).trim(),
    String(farmId).trim(),
    String(plotId).trim(),
    bodyHash,
    String(timestamp).trim(),
    String(nonce).trim(),
    String(keyVersion).trim(),
  ].join("\n");
}

export function computeHmacSignature(canonicalString, secret) {
  return crypto
    .createHmac("sha256", secret)
    .update(canonicalString, "utf8")
    .digest("hex");
}
