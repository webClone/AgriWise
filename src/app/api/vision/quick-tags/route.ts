import { NextResponse } from 'next/server';
import { GoogleGenerativeAI } from '@google/generative-ai';
import { authenticatedUserId } from '@/lib/tenant-authorization';
import { parseDataImageUrl } from '@/lib/image-validation';

const MAX_VISION_IMAGE_BYTES = 6 * 1024 * 1024;

export async function POST(req: Request) {
  try {
    if (!(await authenticatedUserId())) {
      return NextResponse.json({ error: 'Authentication required' }, { status: 401 });
    }
    const body = await req.json();
    const { imageBase64 } = body;
    const image = parseDataImageUrl(imageBase64, MAX_VISION_IMAGE_BYTES);
    if (!image) {
      return NextResponse.json(
        { error: 'A valid JPEG, PNG, or WebP image up to 6 MB is required' },
        { status: 400 },
      );
    }

    if (!process.env.GEMINI_API_KEY) {
       return NextResponse.json({ error: 'Vision analysis is not configured' }, { status: 503 });
    }
    const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);

    // Initialize the model - gemini-1.5-flash is optimized for speed and multimodal tasks
    const model = genAI.getGenerativeModel({ model: "gemini-1.5-flash" });

    const prompt = `
You are an expert agronomist AI analyzing an agricultural field photo.
Provide a structured analysis returning ONLY valid JSON with exactly these fields:
{
  "tags": ["tag1", "tag2", "tag3"], // 3-5 short, descriptive agronomic tags (e.g. "chlorosis", "waterlogging", "healthy_canopy")
  "interpretation": "A short 1-2 sentence interpretation of the image from an agronomic perspective.",
  "confidence": 0.85 // A float between 0.0 and 1.0 indicating your confidence
}
Ensure the output is raw JSON without markdown formatting like \`\`\`json.
`;

    const imageParts = [
      {
        inlineData: {
          data: image.base64,
          mimeType: image.mimeType,
        }
      }
    ];

    const result = await model.generateContent([prompt, ...imageParts]);
    const responseText = result.response.text();
    
    // Parse the JSON output (stripping markdown if the model hallucinated it)
    const cleanedText = responseText.replace(/```json\n?|\n?```/g, '').trim();
    
    let parsedData: unknown;
    try {
      parsedData = JSON.parse(cleanedText);
    } catch (e) {
      console.error("Failed to parse Gemini response:", cleanedText);
      return NextResponse.json({ error: 'Vision service returned an invalid result' }, { status: 502 });
    }
    const candidate = parsedData as Record<string, unknown>;
    const tags = Array.isArray(candidate.tags)
      ? candidate.tags.filter((tag): tag is string => typeof tag === 'string' && tag.length <= 64).slice(0, 10)
      : [];
    const interpretation = typeof candidate.interpretation === 'string'
      ? candidate.interpretation.slice(0, 1_000)
      : '';
    const confidence = Number(candidate.confidence);
    if (!tags.length || !interpretation || !Number.isFinite(confidence)) {
      return NextResponse.json({ error: 'Vision service returned an invalid result' }, { status: 502 });
    }
    return NextResponse.json({
      tags,
      interpretation,
      confidence: Math.min(1, Math.max(0, confidence)),
      authority: 'advisory_unverified',
    });
  } catch (error) {
    console.error('Vision API Error:', error);
    return NextResponse.json(
      { error: 'Failed to analyze image' },
      { status: 500 }
    );
  }
}
