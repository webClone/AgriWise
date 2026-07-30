import { NextResponse } from "next/server";

// Pillow-verified transparent 1x1 RGBA PNG. Keep this centralized so every
// raster proxy returns a decodable image when an upstream provider is down.
const TRANSPARENT_PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNgYGBgAAAABQABeqhXUAAAAABJRU5ErkJggg==",
  "base64"
);

function hasRasterSignature(bytes: Uint8Array): boolean {
  const isPng =
    bytes.length >= 8 &&
    bytes[0] === 0x89 &&
    bytes[1] === 0x50 &&
    bytes[2] === 0x4e &&
    bytes[3] === 0x47 &&
    bytes[4] === 0x0d &&
    bytes[5] === 0x0a &&
    bytes[6] === 0x1a &&
    bytes[7] === 0x0a;
  const isJpeg =
    bytes.length >= 3 &&
    bytes[0] === 0xff &&
    bytes[1] === 0xd8 &&
    bytes[2] === 0xff;
  const isGif =
    bytes.length >= 6 &&
    bytes[0] === 0x47 &&
    bytes[1] === 0x49 &&
    bytes[2] === 0x46 &&
    bytes[3] === 0x38;
  const isWebP =
    bytes.length >= 12 &&
    bytes[0] === 0x52 &&
    bytes[1] === 0x49 &&
    bytes[2] === 0x46 &&
    bytes[3] === 0x46 &&
    bytes[8] === 0x57 &&
    bytes[9] === 0x45 &&
    bytes[10] === 0x42 &&
    bytes[11] === 0x50;

  return isPng || isJpeg || isGif || isWebP;
}

export function isRasterImagePayload(
  buffer: ArrayBuffer,
  contentType: string | null
): boolean {
  const mediaType = contentType?.split(";", 1)[0].trim().toLowerCase() || "";
  return mediaType.startsWith("image/") && hasRasterSignature(new Uint8Array(buffer));
}

export function transparentRasterTile(
  source: string,
  reason: string
): NextResponse {
  const safeReason = reason.replace(/[^a-zA-Z0-9_.-]/g, "_").slice(0, 96);

  return new NextResponse(TRANSPARENT_PNG, {
    status: 200,
    headers: {
      "Content-Type": "image/png",
      "Content-Length": String(TRANSPARENT_PNG.byteLength),
      // Do not retain an outage fallback after provider connectivity recovers.
      "Cache-Control": "no-store, max-age=0",
      "X-Tile-Source": source,
      "X-Tile-Fallback-Reason": safeReason,
    },
  });
}
