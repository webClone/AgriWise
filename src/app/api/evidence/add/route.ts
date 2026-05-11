import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { 
      plotId, 
      zoneId, 
      type, 
      base64Image, 
      notes, 
      date, 
      aiTags = [], 
      aiConfidence = 0, 
      source = "farmer" 
    } = body;

    if (!plotId || !type || !base64Image) {
      return NextResponse.json({ error: 'Missing required fields' }, { status: 400 });
    }

    // Prepare the document payload
    // Using raw command to bypass Prisma replica set restrictions and schema cache issues locally
    const recordData: any = {
      plotId: { $oid: plotId },
      url: base64Image, // In production this would be an S3 URL, but for dev we store the base64 string
      type: type,
      date: { $date: date ? new Date(date).toISOString() : new Date().toISOString() },
      tags: [],
      notes: notes || null,
      aiTags: aiTags,
      aiConfidence: aiConfidence,
      isProcessed: false,
      source: source,
      createdAt: { $date: new Date().toISOString() }
    };

    // Add optional zoneId if provided
    if (zoneId) {
      recordData.zoneId = { $oid: zoneId };
    }

    // Insert using raw MongoDB command for maximum safety across schema changes
    const result = await prisma.$runCommandRaw({
      insert: "PlotPhoto",
      documents: [recordData]
    });

    // --- ASYNC BACKGROUND PROCESSING ---
    // Fire and forget fetch to Python Orchestrator to run Layer 0 farmer_photo pipeline
    const pythonUrl = process.env.AGRIBRAIN_URL || 'http://127.0.0.1:8000';
    fetch(`${pythonUrl}/v2/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        plot_id: plotId,
        mode: "farmer_photo",
        query: "Process new plot evidence",
        days_past: 7,
        days_future: 7,
      })
    }).catch(e => console.error("Async orchestrator trigger failed:", e));

    return NextResponse.json({ success: true, result });
  } catch (error) {
    console.error('Evidence Add Error:', error);
    return NextResponse.json(
      { error: 'Failed to add evidence' },
      { status: 500 }
    );
  }
}
