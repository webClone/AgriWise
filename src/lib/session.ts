/**
 * Session Management — Cookie-based Auth with HMAC-SHA256 Signing
 * ================================================================
 *
 * Flow:
 *   1. OTP verify → createSession() → sets signed cookie
 *   2. Middleware → validateSession() → checks cookie signature
 *   3. Logout → clearSession() → removes cookie
 *
 * Cookie format: base64(payload).base64(hmac-sha256(payload, secret))
 * Payload: { userId, phone, role, exp }
 */
import { cookies } from "next/headers";

const COOKIE_NAME = "agriwise-session";
const SESSION_MAX_AGE = 7 * 24 * 60 * 60; // 7 days in seconds

function getSecret(): string {
  const secret = process.env.AUTH_SECRET;
  if (!secret) {
    if (process.env.NODE_ENV === "production") {
      throw new Error("AUTH_SECRET must be set in production");
    }
    return "dev-secret-do-not-use-in-production";
  }
  return secret;
}

async function sign(payload: string): Promise<string> {
  const secret = getSecret();
  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const signature = await crypto.subtle.sign("HMAC", key, encoder.encode(payload));
  
  // Convert ArrayBuffer signature to base64url
  const bytes = new Uint8Array(signature);
  let binary = "";
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary)
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

interface SessionPayload {
  userId: string;
  phone: string;
  role: string;
  exp: number;
}

/**
 * Create a session cookie after successful OTP verification.
 * Returns the response headers to set the cookie.
 */
export async function createSessionCookie(user: {
  id: string;
  phone: string;
  role: string;
}): Promise<{ name: string; value: string; options: Record<string, unknown> }> {
  const payload: SessionPayload = {
    userId: user.id,
    phone: user.phone,
    role: user.role,
    exp: Math.floor(Date.now() / 1000) + SESSION_MAX_AGE,
  };

  const payloadJson = JSON.stringify(payload);
  const payloadB64 = btoa(payloadJson)
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
  const signature = await sign(payloadB64);
  const token = `${payloadB64}.${signature}`;

  return {
    name: COOKIE_NAME,
    value: token,
    options: {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax" as const,
      path: "/",
      maxAge: SESSION_MAX_AGE,
    },
  };
}

/**
 * Validate session from a cookie value string.
 * Used by middleware (which can't use next/headers cookies()).
 */
export async function validateSessionToken(
  token: string | undefined
): Promise<SessionPayload | null> {
  if (!token) return null;

  const parts = token.split(".");
  if (parts.length !== 2) return null;

  const [payloadB64, signature] = parts;
  const expectedSig = await sign(payloadB64);

  // Constant-time comparison
  if (signature.length !== expectedSig.length) return null;
  let mismatch = 0;
  for (let i = 0; i < signature.length; i++) {
    mismatch |= signature.charCodeAt(i) ^ expectedSig.charCodeAt(i);
  }
  if (mismatch !== 0) return null;

  try {
    const jsonStr = atob(payloadB64.replace(/-/g, "+").replace(/_/g, "/"));
    const payload: SessionPayload = JSON.parse(jsonStr);

    // Check expiry
    if (payload.exp < Math.floor(Date.now() / 1000)) {
      return null;
    }

    return payload;
  } catch {
    return null;
  }
}

/**
 * Get current session from request cookies (for use in API route handlers).
 */
export async function getSession(): Promise<SessionPayload | null> {
  const cookieStore = await cookies();
  const token = cookieStore.get(COOKIE_NAME)?.value;
  return await validateSessionToken(token);
}

/**
 * Cookie deletion descriptor for logout.
 */
export function clearSessionCookie(): {
  name: string;
  value: string;
  options: Record<string, unknown>;
} {
  return {
    name: COOKIE_NAME,
    value: "",
    options: {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax" as const,
      path: "/",
      maxAge: 0,
    },
  };
}
