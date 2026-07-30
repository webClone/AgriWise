import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { ObjectId } from 'bson';
import { authorizePlot } from '@/lib/agribrain/authorize-plot';
import { parseDataImageUrl } from '@/lib/image-validation';

const MAX_EVIDENCE_IMAGE_BYTES = 6 * 1024 * 1024;
const EVIDENCE_TYPES = new Set(['CROP', 'SOIL', 'OVERVIEW', 'DAMAGE', 'OTHER']);
const OBJECT_ID = /^[a-f\d]{24}$/i;

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
      aiConfidence: _clientAiConfidence = 0,
      source: _clientSource = "farmer",
    } = body;

    if (typeof plotId !== 'string' || !plotId || typeof type !== 'string' || !EVIDENCE_TYPES.has(type)) {
      return NextResponse.json({ error: 'Missing required fields' }, { status: 400 });
    }
    const access = await authorizePlot(plotId);
    if (!access.plot) {
      return NextResponse.json(
        { error: access.status === 401 ? 'Authentication required' : 'Plot not found' },
        { status: access.status },
      );
    }
    if (!OBJECT_ID.test(plotId)) {
      return NextResponse.json({ error: 'Invalid plotId' }, { status: 400 });
    }
    if (zoneId != null && (typeof zoneId !== 'string' || !OBJECT_ID.test(zoneId))) {
      return NextResponse.json({ error: 'Invalid zoneId' }, { status: 400 });
    }
    const image = parseDataImageUrl(base64Image, MAX_EVIDENCE_IMAGE_BYTES);
    if (!image) {
      return NextResponse.json(
        { error: 'A valid JPEG, PNG, or WebP image up to 6 MB is required' },
        { status: 400 },
      );
    }
    const observationDate = date ? new Date(date) : new Date();
    if (!Number.isFinite(observationDate.getTime())) {
      return NextResponse.json({ error: 'Invalid observation date' }, { status: 400 });
    }
    const safeNotes = typeof notes === 'string' ? notes.trim().slice(0, 2_000) : null;
    const safeAiTags = Array.isArray(aiTags)
      ? aiTags.filter((tag): tag is string => typeof tag === 'string' && tag.length <= 64).slice(0, 10)
      : [];
    const canonicalImage = `data:${image.mimeType};base64,${image.base64}`;

    // Prepare the document payload
    // Using raw command to bypass Prisma replica set restrictions and schema cache issues locally
    const recordData: any = {
      plotId: new ObjectId(plotId),
      url: canonicalImage,
      type: type,
      date: { $date: observationDate.toISOString() },
      tags: [],
      notes: safeNotes,
      aiTags: safeAiTags,
      // Browser-returned model tags are advisory until independently verified.
      aiConfidence: 0,
      isProcessed: false,
      source: 'farmer',
      createdAt: { $date: new Date().toISOString() }
    };

    // Add optional zoneId if provided
    if (zoneId) {
      recordData.zoneId = new ObjectId(zoneId);
    }

    // Insert using raw MongoDB command for maximum safety across schema changes
    const result = await prisma.$runCommandRaw({
      insert: "PlotPhoto",
      documents: [recordData]
    });

    // The old fire-and-forget call used an unsupported mode and omitted the
    // required context envelope. The evidence is deliberately left pending;
    // the next authorized Layer 0 run admits it through the normal lineage path.
    return NextResponse.json({
      success: true,
      result,
      processing: {
        status: 'pending_next_authorized_run',
        authority: 'farmer_observation',
      },
    });
  } catch (error) {
    console.error('Evidence Add Error:', error);
    return NextResponse.json(
      { error: 'Failed to add evidence' },
      { status: 500 }
    );
  }
}
