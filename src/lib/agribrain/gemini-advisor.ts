// AgriBrain - Google Gemini AI Integration
// Free AI-powered agricultural advice
'use server';

import { GoogleGenerativeAI } from "@google/generative-ai";
import { FAOIntelligenceProfile } from "./fao-data-service";

// Expert agriculture consultant system prompt
const SYSTEM_PROMPT = `You are an expert agricultural consultant with decades of experience in:
- Crop science and agronomy
- Soil management and fertility
- Irrigation systems and water management
- Integrated pest management (IPM)
- Precision agriculture and smart farming
- Climate-smart agriculture
- Post-harvest handling and storage
- Agricultural economics and farm management
- Sustainable and organic farming practices

Your role is to:
1. Provide expert-level guidance on complex agricultural challenges
2. Explain concepts clearly, from basic to advanced levels
3. Give practical, actionable recommendations
4. Consider local conditions and constraints
5. Suggest innovative solutions and best practices
6. Help diagnose problems from descriptions
7. Guide farmers through decision-making processes

Respond in the same language as the user's question. If they write in Arabic, respond in Arabic. If in English, respond in English.
Be thorough but concise. Use bullet points and structured formatting when helpful.`;

interface ChatMessage {
  role: "user" | "model";
  content: string;
}

interface FarmContext {
  cropCode?: string;
  cropNameAr?: string;
  wilayaCode?: string;
  wilayaName?: string;
  plotArea?: number;
  irrigationType?: string;
  soilType?: string;
  growthStage?: string;
  soilProfile?: {
    texture: string;
    ph: number;
    clay: number;
    sand: number;
    organicCarbon: number;
    cnRatio: number;
    cec: number;
    nitrogen: number;
    mineralogy: string;
    hydraulics: {
        awc: number;
        fieldCapacity: number;
        wiltingPoint: number;
    };
    subsoil: {
        clay: number;
        ph: number;
        carbon: number;
    };
  };
}

// Get Gemini client - initialized at runtime
function getGeminiClient() {
  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey || apiKey.trim() === "") {
    console.error("GEMINI_API_KEY is missing in server environment");
    return null;
  }
  return new GoogleGenerativeAI(apiKey);
}

export async function getAIAdvice(
  userMessage: string,
  chatHistory: ChatMessage[] = [],
  farmContext?: FarmContext
): Promise<{ success: boolean; response: string; error?: string }> {
  const genAI = getGeminiClient();
  
  if (!genAI) {
    return getFallbackResponse(userMessage);
  }

  try {
    const model = genAI.getGenerativeModel({ model: "gemini-3-flash-preview" });

    // Build conversation with system prompt and history
    let fullPrompt = SYSTEM_PROMPT + "\n\n";
    
    // Add chat history for context
    if (chatHistory.length > 0) {
      fullPrompt += "Previous conversation:\n";
      for (const msg of chatHistory.slice(-10)) {
        fullPrompt += `${msg.role === "user" ? "User" : "Expert"}: ${msg.content}\n`;
      }
      fullPrompt += "\n";
    }
    
    // Add current user message
    fullPrompt += `User: ${userMessage}\n\nExpert:`;

    console.log("Sending to Gemini...");
    const result = await model.generateContent(fullPrompt);
    const response = result.response.text();
    console.log("Response received");

    return {
      success: true,
      response: response.trim(),
    };
  } catch (error) {
    console.error("Gemini error:", error);
    const errorMessage = error instanceof Error ? error.message : String(error);
    
    if (errorMessage.includes("quota") || errorMessage.includes("429")) {
      return { success: false, response: "", error: "Rate limit exceeded. Try again in a minute." };
    }
    
    if (errorMessage.includes("API_KEY") || errorMessage.includes("401") || errorMessage.includes("403")) {
      return { success: false, response: "", error: "Invalid API key." };
    }

    return { success: false, response: "", error: `Error: ${errorMessage.substring(0, 100)}` };
  }
}

// Fallback responses when API is unavailable
function getFallbackResponse(question: string): { success: boolean; response: string; error?: string } {
  const q = question.toLowerCase();
  
  const responses: { keywords: string[]; response: string }[] = [
    {
      keywords: ["سعر", "اسعار", "ثمن"],
      response: "أسعار المحاصيل في الجزائر (تقريبية):\n\n🌾 القمح: 5,000-7,000 دج/قنطار\n🌾 الشعير: 4,500-6,000 دج/قنطار\n🥔 البطاطا: 30-60 دج/كغ\n🍅 الطماطم: 40-80 دج/كغ\n🧅 البصل: 30-50 دج/كغ\n\nتختلف الأسعار حسب الموسم والمنطقة.",
    },
    {
      keywords: ["ري", "سقي", "ماء", "مياه"],
      response: "نصائح الري:\n\n💧 القمح: ري كل 7-10 أيام في الشتاء\n💧 البطاطا: ري منتظم، التربة رطبة دائماً\n💧 الطماطم: ري يومي في الصيف\n\n⏰ أفضل وقت للري: الصباح الباكر (5-7 صباحاً)",
    },
    {
      keywords: ["سماد", "تسميد", "أسمدة"],
      response: "نصائح التسميد:\n\n🌱 قبل الزراعة: سماد عضوي (10 طن/هكتار)\n🌱 بعد الإنبات (21 يوم): يوريا (100 كغ/هكتار)\n🌱 مرحلة الإزهار: NPK متوازن\n\n⚠️ لا تسمد في الحر الشديد",
    },
    {
      keywords: ["آفة", "آفات", "حشرة", "مرض", "امراض"],
      response: "الآفات الشائعة في الجزائر:\n\n🐛 المن: استخدم صابون زراعي\n🦗 الجراد: بلغ السلطات فوراً\n🍂 البياض: مبيد فطري نحاسي\n\n✅ الوقاية: تناوب المحاصيل ومراقبة منتظمة",
    },
    {
      keywords: ["زراعة", "متى", "موعد", "وقت"],
      response: "مواعيد الزراعة في الجزائر:\n\n🌾 القمح: أكتوبر-نوفمبر\n🌾 الشعير: أكتوبر-نوفمبر\n🥔 البطاطا: مارس-أبريل أو سبتمبر\n🍅 الطماطم: مارس-أبريل\n🧅 البصل: نوفمبر-ديسمبر",
    },
  ];

  for (const item of responses) {
    if (item.keywords.some(keyword => q.includes(keyword))) {
      return { success: true, response: item.response };
    }
  }

  return {
    success: true,
    response: "أنا هنا لمساعدتك! يمكنني الإجابة عن:\n\n• أسعار المحاصيل\n• مواعيد الزراعة\n• الري والتسميد\n• مكافحة الآفات\n\nاكتب سؤالك وسأحاول مساعدتك.",
  };
}

// Generate specific agricultural advice
export async function generateCropAdvice(
  cropCode: string,
  question: string,
  context?: FarmContext
): Promise<string> {
  const cropNames: Record<string, string> = {
    wheat: "القمح",
    barley: "الشعير",
    potato: "البطاطا",
    tomato: "الطماطم",
    olive: "الزيتون",
    date: "التمور",
    onion: "البصل",
  };

  const cropName = cropNames[cropCode] || cropCode;
  const result = await getAIAdvice(
    `بخصوص زراعة ${cropName}: ${question}`,
    [],
    { ...context, cropCode, cropNameAr: cropName }
  );

  return result.success ? result.response : result.error || "حدث خطأ";
}

// Quick advice for common questions
export async function getQuickAdvice(
  topic: "irrigation" | "fertilizer" | "pests" | "harvest" | "weather",
  cropCode: string,
  context?: FarmContext
): Promise<string> {
  const prompts: Record<string, string> = {
    irrigation: "ما هي أفضل طريقة للري وكم مرة يجب أن أسقي؟",
    fertilizer: "ما هو أفضل سماد وكيف أستخدمه؟",
    pests: "ما هي الآفات الشائعة وكيف أكافحها؟",
    harvest: "متى يكون أفضل وقت للحصاد؟",
    weather: "كيف أحمي المحصول من تقلبات الطقس؟",
  };

  return generateCropAdvice(cropCode, prompts[topic], context);
}

// Structure for AI Generated Plan
export interface AIStage {
  stageName: string;
  stageNameAr: string;
  startDay: number;
  endDay: number;
  tasks: {
    title: string;
    titleAr: string;
    descriptionAr?: string;
    dayOffset: number; // days from start of cycle
    type: "PLANTING" | "IRRIGATION" | "FERTILIZING" | "PEST_CONTROL" | "PRUNING" | "WEEDING" | "HARVEST" | "SOIL_PREP" | "OTHER";
  }[];
}

export async function generateAICropPlan(
  cropName: string,
  context: FarmContext,
  profile?: FAOIntelligenceProfile
): Promise<AIStage[]> {
  const genAI = getGeminiClient();
  if (!genAI) throw new Error("AI Client not initialized");

  // Models to try in order of preference
  const CANDIDATE_MODELS = [
    "gemini-3-flash-preview",
    "gemini-3-flash-exp",
    "gemini-2.0-flash-exp", 
    "gemini-1.5-pro",
    "gemini-1.5-flash",
    "gemini-pro"
  ];

  let detailedContext = "";
  if (profile) {
      // Pre-calculate specific directives to FORCE the AI to respect the data
      const directives = [];
      
      if (profile.soil.ph < 6.0) directives.push("CRITICAL: Soil is ACIDIC (pH " + profile.soil.ph + "). You MUST schedule a 'Liming Application' 2 weeks before planting.");
      if (profile.soil.ph > 8.0) directives.push("CRITICAL: Soil is ALKALINE (pH " + profile.soil.ph + "). Recommend Sulfur or Acidifying fertilizers.");
      
      if (profile.soil.clay > 40) directives.push("CRITICAL: HIGH CLAY CONTENT (" + profile.soil.clay + "%). Risk of compaction. Schedule 'Deep Tillage' and 'Gypsum Application' during soil prep.");
      if (profile.soil.sand > 60) directives.push("CRITICAL: SANDY SOIL (" + profile.soil.sand + "%). Low nutrient retention. Split Nitrogen applications into 3-4 smaller doses.");
      
      if (profile.soil.awc < 12) directives.push("CRITICAL: LOW WATER CAPACITY (AWC " + profile.soil.awc + "%). Soil dries fast. Increase irrigation frequency by 30% vs standard.");
      
      if (profile.soil.cnRatio > 25) directives.push("WARNING: High C:N Ratio (" + profile.soil.cnRatio + "). Nitrogen immobilization risk. Add extra Nitrogen starter.");
      
      if (profile.climate.aridityIndex < 0.2) directives.push("CONTEXT: Climate is ARID. Mulching is mandatory to conserve moisture.");

      detailedContext = `
      **HYPER-LOCALIZED FIELD DATA (STRICT ADHERENCE REQUIRED):**
      - Soil Texture: ${profile.soil.textureClass} (Clay: ${profile.soil.clay}%, Sand: ${profile.soil.sand}%)
      - Chemistry: pH ${profile.soil.ph}, CEC ${profile.soil.cec} cmol/kg, Organic Carbon ${profile.soil.organicCarbon}%
      - Hydraulics: AWC ${profile.soil.hydraulics.awc || profile.soil.awc}% (Wilting Point: ${profile.soil.hydraulics.wiltingPoint || 0}%)
      - Climate: GDD ${profile.climate.growingDegreeDays}, Aridity: ${profile.climate.aridityIndex}
      
      **MANDATORY ADAPTATIONS (DO NOT IGNORE):**
      ${directives.map((d, i) => `${i + 1}. ${d}`).join("\n      ")}
      
      **Real-Time Conditions:**
      ${profile.realTime ? `- Current Delta-T: ${profile.realTime.deltaT.toFixed(1)}°C (If > 8, warning: High Evaporation)` : ""}
      `;
  }

  const basePrompt = `
    Act as a **Precision Agronomist** for a specific plot in Algeria.
    Generate a **Scientific and Data-Driven** crop schedule for "${cropName}".
    
    **PLOT CONTEXT:**
    - Region: ${context.wilayaName || context.wilayaCode || "Algeria"}
    - Area: ${context.plotArea || 0} hectares
    - Current Stage: ${context.growthStage || "Planning"}
    ${detailedContext}

    **STRICT RULES:**
    1. **NO GENERIC ADVICE.** Every task must be justified by the Soil/Climate data above.
    2. **Quantify Everything.** Don't say "Apply fertilizer". Say "Apply NPK (due to low P index)".
    3. **DUAL UNITS (CRITICAL):** For every input (Fertilizer, Water, Seeds), specificy the amount **PER HECTARE** and **TOTAL FOR PLOT (${context.plotArea || 0} ha)**.
       Example: "Apply Urea: 100kg/ha (Total: ${((context.plotArea || 1) * 100).toFixed(0)}kg)"
    4. **Dates are Relative.** Day 0 = Planting Date. Use negative days for Soil Prep.
    5. **Safety First.** If Delta-T is high, schedule irrigation at NIGHT.
    
    **CRITICAL**: Return ONLY a valid JSON array.

    **CRITICAL**: Return ONLY a valid JSON array of stages.
    
    Requirements:
    1. **Detail**: Include specific tasks for every stage (e.g., "Deep ploughing to 30cm", "Apply NPK 15-15-15 at 200kg/ha").
    2. **Realism**: Timelines must be accurate for the Algerian climate. Dates should be relative to planting day 0.
    3. **Completeness**: Cover Soil Prep, Sowing, Irrigation (frequency), Fertilization (dates), Pest Monitoring, and Harvest.
    4. **Quantity**: Provide at least 8-10 distinct tasks across the cycle.
    
    JSON Structure:
    [
      {
        "stageName": "English Name",
        "stageNameAr": "Arabic Name",
        "startDay": 0, 
        "endDay": 10,
        "tasks": [
          {
            "title": "English Title",
            "titleAr": "Arabic Title",
            "descriptionAr": "Detailed Arabic description of the task",
            "dayOffset": 0, 
            "type": "PLANTING" // Valid types: PLANTING, IRRIGATION, FERTILIZING, PEST_CONTROL, PRUNING, WEEDING, HARVEST, SOIL_PREP, OTHER
          }
        ]
      }
    ]
  `;

  let lastError: any;

  // Try each model until one works or we run out
  for (const modelName of CANDIDATE_MODELS) {
    try {
        console.log(`AI Generation Attempt with model: ${modelName}`);
        
        // Log attempt start
        try {
            const fs = require('fs');
            const path = require('path');
            const logPath = path.join(process.cwd(), 'debug_log.txt');
            fs.appendFileSync(logPath, `\n[AI Attempt] trying model: ${modelName} for ${cropName}...\n`);
        } catch (e) {}

        const model = genAI.getGenerativeModel({ 
            model: modelName,
            generationConfig: { 
                responseMimeType: "application/json",
                maxOutputTokens: 8192 // Prevent JSON truncation
            }
        });

        const result = await model.generateContent(basePrompt);
        const text = result.response.text();
        
        const jsonStr = text.replace(/```json/g, "").replace(/```/g, "").trim();
        const plan = JSON.parse(jsonStr) as AIStage[];

        // Validate Plan Quality
        const totalTasks = plan.reduce((acc, stage) => acc + (stage.tasks?.length || 0), 0);
        
        if (totalTasks < 6) {
            const msg = `Model ${modelName} returned too few tasks (${totalTasks}). Required > 6.`;
            console.warn(msg);
            
            // Log the "bad" response for analysis
            try {
                const fs = require('fs');
                const path = require('path');
                const logPath = path.join(process.cwd(), 'debug_log.txt');
                fs.appendFileSync(logPath, `[AI Invalid] ${msg}\nRaw Plan Preview: ${JSON.stringify(plan).substring(0, 500)}...\n`);
            } catch (e) {}
            
            throw new Error(msg);
        }

        // Log success
        try {
            const fs = require('fs');
            const path = require('path');
            const logPath = path.join(process.cwd(), 'debug_log.txt');
            fs.appendFileSync(logPath, `[AI Success] Used ${modelName}: Generated ${totalTasks} tasks in ${plan.length} stages.\n`);
        } catch (e) {}

        return plan; // Success!

    } catch (error) {
        console.error(`Model ${modelName} failed:`, error);
        lastError = error;
        
        // Log failure with Raw details if available
        try {
            const fs = require('fs');
            const path = require('path');
            const logPath = path.join(process.cwd(), 'debug_log.txt');
            fs.appendFileSync(logPath, `\n[AI Fail] Model ${modelName} Error: ${String(error)}\n`);
        } catch (e) {}
        
        // Wait longer before retry to give API breathing room
        await new Promise(res => setTimeout(res, 5000));
    }
  }

  // If all models fail, throw the last error to trigger fallback
  throw lastError || new Error("Failed to generate AI plan with any available model");
}

export async function generateLandAnalysis(
  profile: FAOIntelligenceProfile, 
  cropName: string
): Promise<string> {
   const genAI = getGeminiClient();
   if (!genAI) return "⚠️ AI Service Unavailable: GEMINI_API_KEY is missing. Please check your server environment variables.";

   const model = genAI.getGenerativeModel({ model: "gemini-3-flash-preview" });
   
   const prompt = `
     Act as a Senior Soil Scientist and Agronomist. 
     Analyze the following DETAILED soil profile AND REAL-TIME TELEMETRY for a farm growing **${cropName}**.
     
     **PART A: STATIC SOIL DATA**
     - Texture: ${profile.soil.textureClass} (Sand: ${profile.soil.sand}%, Clay: ${profile.soil.clay}%, Silt: ${profile.soil.silt}%)
     - Chemistry: pH ${profile.soil.ph}, Organic Carbon ${profile.soil.organicCarbon}%, Nitrogen ${profile.soil.nitrogen} g/kg
     - Derived Indices: **C:N Ratio ${profile.soil.cnRatio}**, **CEC ${profile.soil.cec} cmol/kg**, Mineralogy: **${profile.soil.mineralogyClass}**
     - Hydraulics: AWC ${profile.soil.awc}%, Field Capacity ${profile.soil.wv0033}%, Wilting Point ${profile.soil.wv1500}%
     - Stratification (30-100cm): Delta Clay ${(profile.subsoil.clay - profile.soil.clay).toFixed(1)}%, Subsoil pH ${profile.subsoil.ph}

     ${profile.realTime ? `
     **PART B: LIVE FIELD TELEMETRY (Right Now)**
     - Atmosphere: ${profile.realTime.temp}°C, Humidity ${profile.realTime.humidity}%, Rain (1h) ${profile.realTime.rain}mm
     - Wind & Energy: Speed ${profile.realTime.windSpeed} km/h, Gusts ${profile.realTime.windGusts} km/h, UV Index ${profile.realTime.uvIndex}
     - Physics: **Delta-T ${profile.realTime.deltaT.toFixed(1)}°C**, **VPD ${profile.realTime.vpd} kPa**, ET0 ${profile.realTime.et0} mm/day
     - Soil Status: 
        - Surface Temp: ${profile.realTime.soilTemp}°C / Deep Temp: ${profile.realTime.soilTemp54}°C
        - Surface Tension (0-30cm): ${(profile.realTime.soilTension / 1000).toFixed(2)} MPa
        - Deep Moisture (27-81cm): ${profile.realTime.deepSoilMoisture} m³/m³
     ` : "**PART B: LIVE TELEMETRY UNAVAILABLE**"}

     **PART C: AGRO-CLIMATIC CONTEXT (Long Term)**
     - Thermal Potency: **Growing Degree Days (GDD): ${profile.climate.growingDegreeDays}**
     - Stress Factors: **Aridity Index ${profile.climate.aridityIndex}**, Drought Risk: **${profile.climate.droughtRisk}**, Erosion Risk: **${profile.climate.erosionRisk}**
     
     **REQUIRED OUTPUT:**
     Provide a concise 5-part Technical Report (Markdown):

     ### 1. Root Zone Mechanics & Mineralogy 🧱
     - Assess compaction risk (Clay % & Mineralogy).
     - Subsoil 'Hardpan' check (Clay delta).

     ### 2. Nutrient Mobility Engine ⚗️
     - C:N Ratio (${profile.soil.cnRatio}) analysis (N-Lockup risk?).
     - pH/CEC Nutrient availability check.

     ### 3. Precision Water Strategy 💧
     - Irrigation Interval advice based on AWC (${profile.soil.awc}%) and Texture.

     ### 4. Climate Resilience & Crop Suitability 🌤️
     - GDD (${profile.climate.growingDegreeDays}) analysis: Is this sufficient for **${cropName}** maturity?
     - Drought/Erosion Mitigation strategy based on risk profile.

     ### 5. Real-Time Physics Alert ⚡ (${profile.realTime ? "LIVE" : "OFFLINE"})
     ${profile.realTime ? `
     - **Spraying Condition**: Is Delta-T (${profile.realTime.deltaT.toFixed(1)}) and Wind (${profile.realTime.windSpeed} km/h) safe?
      - **Disease Risk**: Evaluate VPD (${profile.realTime.vpd}).
     - **Water Stress**: Analyze Soil Tension (${(profile.realTime.soilTension / 1000).toFixed(2)} MPa) vs ET0 demand (${profile.realTime.et0} mm).
     ` : "- Live data was not provided."}
   `;

   try {
     const result = await model.generateContent(prompt);
     return result.response.text();
   } catch (e) {
     console.error("Analysis generation failed", e);
     return "Could not generate analysis at this time.";
   }
}

// ============================================================================
// AI-POWERED CROP SUITABILITY ANALYSIS
// ============================================================================

export interface CropSuitabilityResult {
  suitabilityScore: number;        // 0-100
  suitabilityClass: 'Highly Suitable' | 'Moderately Suitable' | 'Marginally Suitable' | 'Unsuitable';
  potentialYieldRainfed: number;   // t/ha
  potentialYieldIrrigated: number; // t/ha
  limitingFactors: string[];
  recommendations: string[];
  confidence: 'High' | 'Medium' | 'Low';
  reasoning: string;
}

export async function generateCropSuitabilityAnalysis(
  profile: FAOIntelligenceProfile,
  cropCode: string,
  cropName: string
): Promise<CropSuitabilityResult | null> {
  const genAI = getGeminiClient();
  if (!genAI) {
    console.error("AI Client not available for suitability analysis");
    return null;
  }

  console.log("[AI Suitability] Starting analysis for", cropName);
  
  const model = genAI.getGenerativeModel({ 
    model: "gemini-3-flash-preview",
    generationConfig: { 
      responseMimeType: "application/json",
      maxOutputTokens: 2048
    }
  });

  const prompt = `
You are an expert agronomist specializing in Algerian agriculture.
Analyze the following soil and climate data to calculate REALISTIC crop suitability for **${cropName}** (${cropCode}).

**CRITICAL CONTEXT: This is Algeria.** Use realistic Algerian yield statistics:
- Wheat: Rainfed 1.5-3.0 t/ha, Irrigated 3.5-5.0 t/ha
- Barley: Rainfed 1.2-2.5 t/ha, Irrigated 3.0-4.5 t/ha
- Tomato: Open field 15-30 t/ha, Irrigated 35-50 t/ha
- Potato: Rainfed 12-20 t/ha, Irrigated 25-40 t/ha
- Date Palm: 4-8 t/ha, Irrigated oasis 8-12 t/ha
- Olive: 1.5-3.0 t/ha, Irrigated 3-5 t/ha
- Chickpea: 0.8-1.5 t/ha, Irrigated 1.5-2.5 t/ha
- Onion: 15-25 t/ha, Irrigated 30-45 t/ha
- Watermelon: 20-35 t/ha, Irrigated 40-60 t/ha

**SOIL DATA:**
- Texture: ${profile.soil.textureClass} (Clay: ${profile.soil.clay}%, Sand: ${profile.soil.sand}%, Silt: ${profile.soil.silt}%)
- pH: ${profile.soil.ph}
- Organic Carbon: ${profile.soil.organicCarbon}%
- CEC: ${profile.soil.cec} cmol/kg
- Nitrogen: ${profile.soil.nitrogen} g/kg
- Available Water Capacity (AWC): ${profile.soil.awc}%
- Bulk Density: ${profile.soil.bulkDensity} g/cm³
- Mineralogy: ${profile.soil.mineralogyClass}
- P Index: ${profile.soil.phosphorusIndex}, K Index: ${profile.soil.potassiumIndex}

**CLIMATE DATA:**
- Annual Rainfall: ${profile.water.annualRainfall} mm
- Drought Risk Index: ${profile.water.stressIndex}/10
- Growing Degree Days: ${profile.climate.growingDegreeDays}
- Aridity Index: ${profile.climate.aridityIndex}
- Drought Risk: ${profile.climate.droughtRisk}

**CROP REQUIREMENTS for ${cropName}:**
Evaluate if soil pH, texture, water availability, and climate match the crop's needs.

**RETURN JSON with this EXACT structure:**
{
  "suitabilityScore": <number 0-100>,
  "suitabilityClass": "<Highly Suitable|Moderately Suitable|Marginally Suitable|Unsuitable>",
  "potentialYieldRainfed": <realistic number in t/ha for Algeria>,
  "potentialYieldIrrigated": <realistic number in t/ha for Algeria>,
  "limitingFactors": ["<factor 1>", "<factor 2>"],
  "recommendations": ["<actionable recommendation 1>", "<recommendation 2>"],
  "confidence": "<High|Medium|Low>",
  "reasoning": "<1-2 sentence explanation of the score>"
}

Be REALISTIC. If conditions are poor, give a LOW score. If rainfall is insufficient for high-water crops, reflect that in the score and yield.
`;

  try {
    const result = await model.generateContent(prompt);
    const text = result.response.text();
    const jsonStr = text.replace(/```json/g, "").replace(/```/g, "").trim();
    const analysis = JSON.parse(jsonStr) as CropSuitabilityResult;
    
    // Validate and clamp values
    analysis.suitabilityScore = Math.max(0, Math.min(100, Math.round(analysis.suitabilityScore)));
    analysis.potentialYieldRainfed = Math.max(0, parseFloat(analysis.potentialYieldRainfed.toFixed(1)));
    analysis.potentialYieldIrrigated = Math.max(0, parseFloat(analysis.potentialYieldIrrigated.toFixed(1)));
    
    console.log(`[AI Suitability] ${cropName}: Score ${analysis.suitabilityScore}, Yield ${analysis.potentialYieldRainfed}/${analysis.potentialYieldIrrigated} t/ha`);
    
    return analysis;
  } catch (e) {
    console.error("AI Suitability analysis failed:", e);
    return null;
  }
}
