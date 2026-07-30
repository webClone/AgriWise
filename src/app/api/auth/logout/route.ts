// Auth API - Logout
import { NextResponse } from "next/server";
import { clearSessionCookie } from "@/lib/session";

export async function POST() {
  const cookie = clearSessionCookie();
  const response = NextResponse.json({
    success: true,
    message: "Logged out successfully",
  });

  response.cookies.set(cookie.name, cookie.value, cookie.options as any);
  return response;
}
