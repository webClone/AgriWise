// Pest Reports API - Field reporting and alerts
import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db";

// GET - List pest reports (with optional filters)
export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const wilayaCode = searchParams.get("wilaya");
    const status = searchParams.get("status");
    const type = searchParams.get("type");
    const limit = parseInt(searchParams.get("limit") || "20");

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
    const body = await request.json();
    const { 
      reporterId,
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

    if (!reporterId || !type || !latitude || !longitude || !wilayaCode || !severity) {
      return NextResponse.json(
        { success: false, error: "جميع الحقول المطلوبة يجب ملؤها" },
        { status: 400 }
      );
    }

    const report = await prisma.pestReport.create({
      data: {
        type,
        name,
        nameAr,
        latitude,
        longitude,
        wilayaCode,
        commune,
        severity,
        description,
        photos: photos || [],
        cropAffected,
        spreadArea: spreadArea ? parseFloat(spreadArea) : null,
        reporterId,
      },
    });

    // Check if we should create/update an alert
    await checkAndCreateAlert(wilayaCode, type, name, nameAr, severity, cropAffected);

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
    const body = await request.json();
    const { id, status, verifiedBy, treatment } = body;

    if (!id || !status) {
      return NextResponse.json(
        { success: false, error: "معرف البلاغ والحالة مطلوبان" },
        { status: 400 }
      );
    }

    const report = await prisma.pestReport.update({
      where: { id },
      data: {
        status,
        ...(verifiedBy && { verifiedBy }),
        ...(treatment && { treatment }),
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
