import * as crypto from "crypto";
import {
  buildCanonicalString,
  canonicalizeQueryParams,
  computeHmacSignature,
} from "./internal-service-auth-canonical.mjs";

export interface PlotNamespaceInput {
  tenantId: string;
  farmId: string;
  plotId: string;
}

export function buildSignedInternalHeaders(
  method: string,
  pathname: string,
  namespace: PlotNamespaceInput,
  bodyText: string = "",
  queryParams: Array<[string, string]> | Record<string, string | string[]> | string = ""
): Record<string, string> {
  const secret = process.env.AGRIBRAIN_INTERNAL_SERVICE_SECRET;
  const isProd = process.env.NODE_ENV === "production" || process.env.APP_ENV === "production";

  if (!secret || !secret.trim()) {
    if (isProd) {
      throw new Error("AGRIBRAIN_INTERNAL_SERVICE_SECRET must be set in production environments");
    }
  }

  const effectiveSecret = secret?.trim() || "agribrain-internal-dev-secret-key-32bytes";
  const keyVersion = "v1";
  const nonce = crypto.randomBytes(16).toString("hex");
  const timestamp = Math.floor(Date.now() / 1000).toString();

  const canonicalString = buildCanonicalString({
    method,
    pathname,
    queryString: typeof queryParams === "string" ? queryParams : canonicalizeQueryParams(queryParams),
    tenantId: namespace.tenantId,
    farmId: namespace.farmId,
    plotId: namespace.plotId,
    bodyText,
    timestamp,
    nonce,
    keyVersion,
  });

  const signature = computeHmacSignature(canonicalString, effectiveSecret);

  return {
    "X-AgriBrain-Signature": signature,
    "X-AgriBrain-Timestamp": timestamp,
    "X-AgriBrain-Nonce": nonce,
    "X-AgriBrain-Key-Version": keyVersion,
    "X-Tenant-Id": namespace.tenantId.trim(),
    "X-Farm-Id": namespace.farmId.trim(),
    "X-Plot-Id": namespace.plotId.trim(),
  };
}
