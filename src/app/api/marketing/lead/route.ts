import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { intent, name, email, organization, country, orgType, message, fieldCount } = body;

    if (!name || !email || !organization || !intent) {
      return NextResponse.json(
        { error: "Missing required fields (name, email, organization, intent)" },
        { status: 400 }
      );
    }

    const lead = await prisma.institutionalLead.create({
      data: {
        intent: String(intent),
        name: String(name),
        email: String(email),
        organization: String(organization),
        country: country ? String(country) : "Algeria",
        orgType: orgType ? String(orgType) : undefined,
        message: message ? String(message) : undefined,
        fieldCount: fieldCount ? String(fieldCount) : undefined,
        status: "NEW",
      },
    });

    return NextResponse.json({ success: true, id: lead.id });
  } catch (error: any) {
    console.error("Failed to submit institutional lead:", error);
    return NextResponse.json(
      { error: "Internal server error submitting request" },
      { status: 500 }
    );
  }
}
