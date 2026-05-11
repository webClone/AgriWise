import { NextResponse } from 'next/server';
import { GoogleGenerativeAI } from '@google/generative-ai';

const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY || '');

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { imageBase64 } = body;

    if (!imageBase64) {
      return NextResponse.json({ error: 'No image provided' }, { status: 400 });
    }

    if (!process.env.GEMINI_API_KEY) {
       console.warn("No GEMINI_API_KEY found, returning fallback mock response.");
       return NextResponse.json({
         tags: ["chlorosis", "early_stage", "lower_leaves"],
         interpretation: "Mock response: Possible mild nutrient deficiency or early disease on lower leaves. Canopy development looks patchy.",
         confidence: 0.78
       });
    }

    // Initialize the model - gemini-1.5-flash is optimized for speed and multimodal tasks
    const model = genAI.getGenerativeModel({ model: "gemini-1.5-flash" });

    // Clean base64 string if it has the data URI prefix
    const base64Data = imageBase64.replace(/^data:image\/\w+;base64,/, "");

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
          data: base64Data,
          mimeType: "image/jpeg" // Using a generic image mime type is usually fine for Gemini
        }
      }
    ];

    const result = await model.generateContent([prompt, ...imageParts]);
    const responseText = result.response.text();
    
    // Parse the JSON output (stripping markdown if the model hallucinated it)
    const cleanedText = responseText.replace(/```json\n?|\n?```/g, '').trim();
    
    let parsedData;
    try {
      parsedData = JSON.parse(cleanedText);
    } catch (e) {
      console.error("Failed to parse Gemini response:", cleanedText);
      parsedData = {
        tags: ["unknown"],
        interpretation: "Could not analyze the image clearly.",
        confidence: 0.1
      };
    }

    return NextResponse.json(parsedData);
  } catch (error) {
    console.error('Vision API Error:', error);
    return NextResponse.json(
      { error: 'Failed to analyze image' },
      { status: 500 }
    );
  }
}
