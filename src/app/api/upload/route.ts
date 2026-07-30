import { NextRequest, NextResponse } from "next/server";
import { writeFile, mkdir } from "fs/promises";
import path from "path";
import { randomUUID } from "crypto";
import { authorizePlot } from "@/lib/agribrain/authorize-plot";
import { validateImageBytes } from "@/lib/image-validation";

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();
    const file = formData.get("file") as File | null;
    const plotId = formData.get("plotId");

    if (typeof plotId !== "string" || !plotId) {
      return NextResponse.json({ error: "plotId is required" }, { status: 400 });
    }
    const access = await authorizePlot(plotId);
    if (!access.plot) {
      return NextResponse.json(
        { error: access.status === 401 ? "Authentication required" : "Plot not found" },
        { status: access.status },
      );
    }

    if (!file) {
      return NextResponse.json({ error: "No file provided" }, { status: 400 });
    }

    // Validate file size (10MB max)
    const MAX_SIZE = 10 * 1024 * 1024;
    if (file.size > MAX_SIZE) {
      return NextResponse.json({ error: "File too large (max 10MB)" }, { status: 400 });
    }

    const bytes = await file.arrayBuffer();
    const buffer = Buffer.from(bytes);
    const image = validateImageBytes(buffer, file.type, MAX_SIZE);
    if (!image) {
      return NextResponse.json(
        { error: "Only valid JPEG, PNG, and WebP images are allowed" },
        { status: 400 },
      );
    }

    const filename = `${randomUUID()}.${image.extension}`;
    const uploadDir = path.join(process.cwd(), "public", "uploads", "plots");
    await mkdir(uploadDir, { recursive: true });
    const filepath = path.join(uploadDir, filename);
    await writeFile(filepath, image.bytes, { flag: "wx" });

    // Return the public URL
    const url = `/uploads/plots/${filename}`;
    return NextResponse.json({ success: true, url });

  } catch (error) {
    console.error("Upload error:", error);
    return NextResponse.json({ error: "Upload failed" }, { status: 500 });
  }
}
