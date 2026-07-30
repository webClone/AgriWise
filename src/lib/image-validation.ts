const IMAGE_TYPES = {
  "image/jpeg": "jpg",
  "image/png": "png",
  "image/webp": "webp",
} as const;

export type SupportedImageMime = keyof typeof IMAGE_TYPES;

export interface ValidatedImage {
  bytes: Buffer;
  mimeType: SupportedImageMime;
  extension: (typeof IMAGE_TYPES)[SupportedImageMime];
  base64: string;
}

function hasExpectedSignature(bytes: Uint8Array, mimeType: SupportedImageMime): boolean {
  if (mimeType === "image/jpeg") {
    return bytes.length >= 3 && bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff;
  }
  if (mimeType === "image/png") {
    const signature = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];
    return bytes.length >= signature.length && signature.every((value, index) => bytes[index] === value);
  }
  return bytes.length >= 12
    && bytes[0] === 0x52
    && bytes[1] === 0x49
    && bytes[2] === 0x46
    && bytes[3] === 0x46
    && bytes[8] === 0x57
    && bytes[9] === 0x45
    && bytes[10] === 0x42
    && bytes[11] === 0x50;
}

export function validateImageBytes(
  bytes: Buffer,
  mimeType: string,
  maxBytes: number,
): ValidatedImage | null {
  if (!(mimeType in IMAGE_TYPES) || bytes.length === 0 || bytes.length > maxBytes) return null;
  const supportedMime = mimeType as SupportedImageMime;
  if (!hasExpectedSignature(bytes, supportedMime)) return null;
  return {
    bytes,
    mimeType: supportedMime,
    extension: IMAGE_TYPES[supportedMime],
    base64: bytes.toString("base64"),
  };
}

export function parseDataImageUrl(value: unknown, maxBytes: number): ValidatedImage | null {
  if (typeof value !== "string") return null;
  const match = /^data:(image\/(?:jpeg|png|webp));base64,([A-Za-z0-9+/=\r\n]+)$/.exec(value);
  if (!match) return null;
  const estimatedBytes = Math.floor((match[2].replace(/[\r\n]/g, "").length * 3) / 4);
  if (estimatedBytes > maxBytes + 2) return null;
  try {
    return validateImageBytes(
      Buffer.from(match[2], "base64"),
      match[1],
      maxBytes,
    );
  } catch {
    return null;
  }
}
