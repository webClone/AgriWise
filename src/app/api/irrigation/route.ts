import { NextResponse } from "next/server";
import { authenticatedUserId } from "@/lib/tenant-authorization";

async function requireUser() {
  return Boolean(await authenticatedUserId());
}

/** No actuator gateway is wired to this route yet; never report mock success. */
export async function GET() {
  if (!(await requireUser())) {
    return NextResponse.json({ error: "Authentication required" }, { status: 401 });
  }
  return NextResponse.json({
    status: "unavailable",
    authoritative: false,
    reason: "irrigation_runtime_gateway_not_configured",
  }, { status: 503 });
}

export async function POST() {
  if (!(await requireUser())) {
    return NextResponse.json({ error: "Authentication required" }, { status: 401 });
  }
  return NextResponse.json({
    success: false,
    authoritative: false,
    error: "Irrigation command dispatch is not configured",
  }, { status: 501 });
}
