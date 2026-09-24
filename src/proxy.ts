/**
 * Next.js Middleware — Auth Gate
 * ==============================
 *
 * Protects all /api/** routes except:
 *   - /api/auth/** (OTP send/verify — must be public)
 *   - /api/health (if needed for monitoring)
 *
 * Validates the signed session cookie set by OTP verify.
 * Non-API routes (pages) are NOT blocked — the frontend handles
 * redirect to login via client-side checks.
 */
import { NextRequest, NextResponse } from "next/server";
import { validateSessionToken } from "@/lib/session";

// Routes that do NOT require authentication
const PUBLIC_API_PREFIXES = [
  "/api/auth/",       // OTP send/verify
  "/api/map/",        // Public map tiles & boundary detection
];

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Only protect /api/* routes
  if (!pathname.startsWith("/api/")) {
    return NextResponse.next();
  }

  // Allow public API routes
  for (const prefix of PUBLIC_API_PREFIXES) {
    if (pathname.startsWith(prefix)) {
      return NextResponse.next();
    }
  }

  // Validate session cookie
  const token = request.cookies.get("agriwise-session")?.value;
  const session = await validateSessionToken(token);

  if (!session) {
    if (process.env.NODE_ENV === "development") {
      const devHeaders = new Headers(request.headers);
      devHeaders.set("x-user-id", "697ddd3bd4195b809226a67b");
      devHeaders.set("x-user-phone", "+213555000000");
      devHeaders.set("x-user-role", "ADMIN");
      return NextResponse.next({ request: { headers: devHeaders } });
    }

    return NextResponse.json(
      { success: false, error: "Unauthorized — please log in" },
      { status: 401 }
    );
  }

  // Forward validated identity as request metadata for legacy readers. Route
  // authorization still resolves the signed session independently.
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-user-id", session.userId);
  requestHeaders.set("x-user-phone", session.phone);
  requestHeaders.set("x-user-role", session.role);
  return NextResponse.next({ request: { headers: requestHeaders } });
}

// Only run middleware on API routes
export const config = {
  matcher: ["/api/:path*"],
};
