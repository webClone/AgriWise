// Pest Reports API - Field reporting and alerts
import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { getSession } from "@/lib/session";
import { ObjectId } from "bson";

const REPORT_TYPES = new Set(["pest", "disease", "unknown"]);
const REPORT_STATUSES = new Set(["REPORTED", "VERIFIED", "INVESTIGATING", "RESOLVED", "FALSE_ALARM"]);
const SEVERITIES = new Set(["INFO", "WARNING", "CRITICAL"]);
const REVIEW_ROLES = new Set(["AGRONOMIST", "LOCAL_GOV", "NATIONAL_GOV", "ADMIN"]);

function optionalText(value: unknown, maxLength: number): string | null {
  if (value === undefined || value === null || value === "") return null;
  if (typeof value !== "string") throw new Error("invalid_text");
  const normalized = value.trim();
  if (!normalized || normalized.length > maxLength) throw new Error("invalid_text");
  return normalized;
}

// GET - List pest reports (with optional filters)
export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const wilayaCode = searchParams.get("wilaya");
    const status = searchParams.get("status");
    const type = searchParams.get("type");
    const requestedLimit = Number(searchParams.get("limit") || 20);
    const limit = Number.isInteger(requestedLimit)
      ? Math.min(100, Math.max(1, requestedLimit))
      : 20;

    if (status && !REPORT_STATUSES.has(status)) {
      return NextResponse.json({ success: false, error: "Invalid report status" }, { status: 400 });
    }
    if (type && !REPORT_TYPES.has(type)) {
      return NextResponse.json({ success: false, error: "Invalid report type" }, { status: 400 });
    }

    const where: Record<string, unknown> = {};
    if (wilayaCode) where.wilayaCode = wilayaCode;
    if (status) where.status = status;
    if (type) where.type = type;

    const reports = await prisma.pestReport.findMany({
      where,
      include: {
        reporter: {
          select: { name: true, wilaya: true },
        },
      },
      orderBy: { createdAt: "desc" },
      take: limit,
    });

    // Get summary stats
    const stats = await prisma.pestReport.groupBy({
      by: ["status"],
      _count: true,
      where: wilayaCode ? { wilayaCode } : undefined,
    });

    return NextResponse.json({
      success: true,
      data: {
        reports,
        stats: stats.reduce((acc: Record<string, number>, s: { status: string; _count: number }) => {
          acc[s.status] = s._count;
          return acc;
        }, {} as Record<string, number>),
      },
    });
  } catch (error) {
    console.error("Pest reports GET error:", error);
    return NextResponse.json(
      { success: false, error: "حدث خطأ. حاول مرة أخرى." },
      { status: 500 }
    );
  }
}

// POST - Create a new pest report
export async function POST(request: NextRequest) {
  try {
    const session = await getSession();
    if (!session?.userId) {
      return NextResponse.json({ success: false, error: "Authentication required" }, { status: 401 });
    }
    const body = await request.json();
    const { 
      type, 
      name, 
      nameAr,
      latitude, 
      longitude, 
      wilayaCode,
      commune,
      severity,
      description,
      photos,
      cropAffected,
      spreadArea,
    } = body;

    const numericLatitude = Number(latitude);
    const numericLongitude = Number(longitude);
    const numericSpreadArea = spreadArea === undefined || spreadArea === null || spreadArea === ""
      ? null
      : Number(spreadArea);
    if (
      typeof type !== "string"
      || !REPORT_TYPES.has(type)
      || !Number.isFinite(numericLatitude)
      || numericLatitude < -90
      || numericLatitude > 90
      || !Number.isFinite(numericLongitude)
      || numericLongitude < -180
      || numericLongitude > 180
      || typeof wilayaCode !== "string"
      || !/^\d{1,2}$/.test(wilayaCode)
      || typeof severity !== "string"
      || !SEVERITIES.has(severity)
      || (numericSpreadArea !== null && (!Number.isFinite(numericSpreadArea) || numericSpreadArea < 0 || numericSpreadArea > 1_000_000))
      || (photos !== undefined && (!Array.isArray(photos) || photos.length > 10 || photos.some((photo) => typeof photo !== "string" || photo.length > 2048)))
    ) {
      return NextResponse.json(
        { success: false, error: "Invalid pest report payload" },
        { status: 400 }
      );
    }

    let safeName: string | null;
    let safeNameAr: string | null;
    let safeCommune: string | null;
    let safeDescription: string | null;
    let safeCropAffected: string | null;
    try {
      safeName = optionalText(name, 120);
      safeNameAr = optionalText(nameAr, 120);
      safeCommune = optionalText(commune, 120);
      safeDescription = optionalText(description, 4_000);
      safeCropAffected = optionalText(cropAffected, 120);
    } catch {
      return NextResponse.json({ success: false, error: "Invalid pest report text" }, { status: 400 });
    }

    const report = await prisma.pestReport.create({
      data: {
        type,
        name: safeName,
        nameAr: safeNameAr,
        latitude: numericLatitude,
        longitude: numericLongitude,
        wilayaCode,
        commune: safeCommune,
        severity: severity as "INFO" | "WARNING" | "CRITICAL",
        description: safeDescription,
        photos: photos || [],
        cropAffected: safeCropAffected,
        spreadArea: numericSpreadArea,
        reporterId: session.userId,
      },
    });

    // Check if we should create/update an alert
    await checkAndCreateAlert(wilayaCode, type, safeName, safeNameAr, severity, safeCropAffected);

    return NextResponse.json({
      success: true,
      data: report,
      message: "تم إرسال البلاغ بنجاح. شكراً لمساهمتك!",
    });
  } catch (error) {
    console.error("Pest reports POST error:", error);
    return NextResponse.json(
      { success: false, error: "حدث خطأ. حاول مرة أخرى." },
      { status: 500 }
    );
  }
}

// PUT - Update report status (for admins/agronomists)
export async function PUT(request: NextRequest) {
  try {
    const session = await getSession();
    if (!session?.userId) {
      return NextResponse.json({ success: false, error: "Authentication required" }, { status: 401 });
    }
    if (!REVIEW_ROLES.has(session.role)) {
      return NextResponse.json({ success: false, error: "Reviewer role required" }, { status: 403 });
    }
    const body = await request.json();
    const { id, status, treatment } = body;

    if (
      typeof id !== "string"
      || !ObjectId.isValid(id)
      || typeof status !== "string"
      || !REPORT_STATUSES.has(status)
      || (treatment !== undefined && (typeof treatment !== "string" || treatment.length > 4_000))
    ) {
      return NextResponse.json(
        { success: false, error: "Invalid report update" },
        { status: 400 }
      );
    }

    const existing = await prisma.pestReport.findUnique({
      where: { id },
      select: { id: true },
    });
    if (!existing) {
      return NextResponse.json({ success: false, error: "Report not found" }, { status: 404 });
    }
    const report = await prisma.pestReport.update({
      where: { id: existing.id },
      data: {
        status: status as "REPORTED" | "VERIFIED" | "INVESTIGATING" | "RESOLVED" | "FALSE_ALARM",
        verifiedBy: session.userId,
        ...(treatment !== undefined && { treatment: treatment.trim() || null }),
      },
    });

    return NextResponse.json({
      success: true,
      data: report,
    });
  } catch (error) {
    console.error("Pest reports PUT error:", error);
    return NextResponse.json(
      { success: false, error: "حدث خطأ. حاول مرة أخرى." },
      { status: 500 }
    );
  }
}

// Helper: Check if we need to create/update a regional alert
async function checkAndCreateAlert(
  wilayaCode: string, 
  type: string, 
  name: string | null, 
  nameAr: string | null,
  severity: string,
  cropAffected: string | null
) {
  const thirtyDaysAgo = new Date();
  thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);

  // Count recent reports of same pest in same wilaya
  const reportCount = await prisma.pestReport.count({
    where: {
      wilayaCode,
      type,
      name,
      createdAt: { gte: thirtyDaysAgo },
    },
  });

  // If 3+ reports, create/update an alert
  if (reportCount >= 3) {
    const existingAlert = await prisma.pestAlert.findFirst({
      where: {
        wilayaCode,
        pestName: name || "غير معروف",
        isActive: true,
      },
    });

    if (existingAlert) {
      await prisma.pestAlert.update({
        where: { id: existingAlert.id },
        data: { reportCount },
      });
    } else {
      await prisma.pestAlert.create({
        data: {
          pestName: name || "غير معروف",
          pestNameAr: nameAr || name || "غير معروف",
          type,
          wilayaCode,
          severity: severity as "INFO" | "WARNING" | "CRITICAL",
          titleAr: `تنبيه: انتشار ${nameAr || name || "آفة"}`,
          messageAr: `تم رصد ${reportCount} حالات لـ${nameAr || name || "آفة"} في منطقتك. يُرجى الفحص واتخاذ الإجراءات الوقائية.`,
          affectedCrops: cropAffected ? [cropAffected] : [],
          reportCount,
        },
      });
    }
  }
}
