import { NextRequest, NextResponse } from "next/server";
import { ObjectId } from "bson";
import { prisma } from "@/lib/db";
import { createSessionCookie } from "@/lib/session";

export async function POST(request: NextRequest) {
  if (process.env.NODE_ENV !== "development") {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }
  if (
    request.headers.get("origin") !== request.nextUrl.origin
    || request.headers.get("x-agriwise-dev-bootstrap") !== "plot-page"
    || !["localhost", "127.0.0.1", "::1"].includes(request.nextUrl.hostname)
  ) {
    return NextResponse.json({ error: "Development bootstrap rejected" }, { status: 403 });
  }

  let body: { plotId?: unknown; farmId?: unknown };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid request" }, { status: 400 });
  }
  if (
    typeof body.farmId !== "string"
    || !ObjectId.isValid(body.farmId)
  ) {
    return NextResponse.json({ error: "A valid farmId is required" }, { status: 400 });
  }

  const farm = await prisma.farm.findUnique({
    where: { id: body.farmId },
    select: { id: true, userId: true },
  });
  if (!farm) {
    return NextResponse.json({ error: "Farm not found" }, { status: 404 });
  }

  if (body.plotId !== undefined) {
    if (typeof body.plotId !== "string" || !ObjectId.isValid(body.plotId)) {
      return NextResponse.json({ error: "A valid plotId is required" }, { status: 400 });
    }
    const plot = await prisma.plot.findFirst({
      where: { id: body.plotId, farmId: farm.id },
      select: { id: true },
    });
    if (!plot) {
      return NextResponse.json({ error: "Plot not found" }, { status: 404 });
    }
  }

  const user = await prisma.user.findUnique({
    where: { id: farm.userId },
    select: { id: true, phone: true, role: true },
  });

  const sessionCookie = await createSessionCookie(user || {
    id: farm.userId,
    phone: "dev-local-orphan-owner",
    role: "SMALL_FARMER",
  });
  const response = NextResponse.json({ success: true }, {
    headers: { "Cache-Control": "no-store" },
  });
  response.cookies.set(
    sessionCookie.name,
    sessionCookie.value,
    sessionCookie.options as any,
  );
  return response;
}
