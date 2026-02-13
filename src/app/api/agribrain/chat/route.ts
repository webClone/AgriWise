import { NextRequest, NextResponse } from "next/server";
import { AgriBrainTools, GetFieldIndicatorsSchema, PredictYieldSchema } from "@packages/contracts/tools";
import { z } from "zod";

// --- Configuration ---
const OPENROUTER_API_KEY = "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";
const OPENROUTER_MODEL = "google/gemma-3-27b-it";
// Set to true to attempt connecting to local Python backend
const USE_PYTHON_BACKEND = true; 
const PYTHON_API_URL = "http://127.0.0.1:8000";

// --- Tools Implementation (Server-Side) ---

async function getFieldIndicators(args: z.infer<typeof GetFieldIndicatorsSchema>) {
  console.log("🛠️ Tool Executon: eo_getFieldIndicators", args);
  
  if (USE_PYTHON_BACKEND) {
      try {
          const params = new URLSearchParams({
              field_id: args.fieldId,
              start_date: args.startDate,
              end_date: args.endDate
          });
          const res = await fetch(`${PYTHON_API_URL}/tools/eo/get_field_indicators?${params}`);
          if (res.ok) {
              const data = await res.json();
              console.log("✅ Tool executed via Python Backend");
              return data;
          } else {
             console.warn(`⚠️ Python Backend returned ${res.status}, falling back to mock.`);
          }
      } catch (e) {
          console.warn("⚠️ Could not reach Python Backend (is it running?), falling back to mock.", e);
      }
  }

  // Fallback Logic
  console.log("⚠️ Using Javascript Fallback Logic");
  return [
      {
        field_id: args.fieldId,
        date: args.startDate,
        ndvi: 0.45,
        ndmi: 0.12,
        rainfall_mm: 5.0,
        temp_c: 21.5,
        source: "JS_FALLBACK" 
      },
      {
        field_id: args.fieldId,
        date: args.endDate,
        ndvi: 0.55,
        ndmi: 0.18,
        rainfall_mm: 12.0,
        temp_c: 19.8,
        source: "JS_FALLBACK"
      }
    ];
}

async function predictYield(args: z.infer<typeof PredictYieldSchema>) {
  console.log("🛠️ Tool Executon: ml_predictYield", args);
  
  if (USE_PYTHON_BACKEND) {
      try {
          const res = await fetch(`${PYTHON_API_URL}/tools/ml/predict_yield`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ field_id: args.fieldId, crop: args.crop })
          });
          if (res.ok) {
              const data = await res.json();
              console.log("✅ Tool executed via Python Backend");
              return data;
          }
      } catch (e) {
           console.warn("⚠️ Could not reach Python Backend (is it running?), falling back to mock.");
      }
  }

  const baseYield = args.crop.toLowerCase().includes("wheat") ? 4.5 : 35.0;
  return {
      field_id: args.fieldId,
      crop: args.crop,
      predicted_yield_t_ha: baseYield,
      confidence: 0.88,
      limiting_factors: ["Nitrogen deficiency detected"],
      source: "JS_FALLBACK"
    };
}

// Map tool names to functions
const toolsMap: Record<string, (args: any) => Promise<any>> = {
  "eo_getFieldIndicators": getFieldIndicators,
  "ml_predictYield": predictYield
};

// --- OpenRouter Client ---

async function chatCompletion(messages: any[], tools: any[]): Promise<any> {
    const response = await fetch("https://openrouter.ai/api/v1/chat/completions", {
        method: "POST",
        headers: {
            "Authorization": `Bearer ${OPENROUTER_API_KEY}`,
            "Content-Type": "application/json",
            "HTTP-Referer": "https://carbonic-lore-forceless.ngrok-free.dev", // Required by OpenRouter
            "X-Title": "AgriWise"
        },
        body: JSON.stringify({
            model: OPENROUTER_MODEL,
            messages: messages,
            tools: tools,
            tool_choice: "auto"
        })
    });

    if (!response.ok) {
        const errorText = await response.text();
        console.error("OpenRouter Error:", errorText);
        throw new Error(`OpenRouter API Error: ${response.status} - ${errorText}`);
    }

    return await response.json();
}

// --- Route Handler ---

export async function POST(req: NextRequest) {
  console.log("🚀 AgriBrain Chat Request Received (OpenRouter)");
  try {
    const { message, history, context } = await req.json();
    console.log("📩 User Message:", message);

    if (!message) {
         return NextResponse.json({ error: "Message content cannot be empty" }, { status: 400 });
    }

    // 1. Define Tools (JSON Schema Format for OpenAI/OpenRouter)
    // Note: We construct this manually to match OpenAI format, adapting from Zod logic conceptually
    const tools = [
        {
            type: "function",
            function: {
                name: "eo_getFieldIndicators",
                description: AgriBrainTools.eo_getFieldIndicators.description,
                parameters: {
                    type: "object",
                    properties: {
                        fieldId: { type: "string", description: "Unique UUID of the field" },
                        startDate: { type: "string", description: "YYYY-MM-DD" },
                        endDate: { type: "string", description: "YYYY-MM-DD" },
                        indicators: { type: "array", items: { type: "string" } }
                    },
                    required: ["fieldId", "startDate", "endDate", "indicators"]
                }
            }
        },
        {
            type: "function",
            function: {
                name: "ml_predictYield",
                description: AgriBrainTools.ml_predictYield.description,
                parameters: {
                    type: "object",
                    properties: {
                        fieldId: { type: "string", description: "Unique UUID of the field" },
                        crop: { type: "string", description: "Crop name e.g. wheat, tomato" }
                    },
                    required: ["fieldId", "crop"]
                }
            }
        }
    ];

    // 2. Prepare Context
    let systemInstruction = `You are AgriBrain, a friendly and knowledgeable agricultural AI assistant.

CONVERSATION RULES:
1. Be conversational and friendly. Greet users warmly when they say hi, hello, etc.
2. Answer general questions about farming, crops, and agriculture naturally.
3. ONLY use tools when the user specifically asks about:
   - Field health, NDVI, moisture, or satellite data → use 'eo_getFieldIndicators'
   - Yield prediction or harvest forecasts → use 'ml_predictYield'
4. For casual conversation, just respond naturally without using any tools.
5. If you use a tool, explain the results in a helpful, human-readable way.
6. DO NOT re-introduce yourself in every message. Only greet once at the start.

You have access to these tools:
- eo_getFieldIndicators: Get satellite-based field health data (NDVI, moisture, etc.)
- ml_predictYield: Predict crop yield using machine learning

Current Context:`;
    
    if (context) {
        systemInstruction += `\n\n**CURRENT PLOT CONTEXT:**\n`;
        if (context.cropCode) systemInstruction += `- Crop: ${context.cropCode}\n`;
        if (context.farmCoordinates) systemInstruction += `- Coordinates: Lat ${context.farmCoordinates.lat}, Lng ${context.farmCoordinates.lng}\n`;
        
        if (context.data) {
           const d = context.data;
           
           // REAL-TIME TELEMETRY
           if (d.realTime) {
               systemInstruction += `\n**REAL-TIME FIELD TELEMETRY:**\n`;
               systemInstruction += `- Temperature: ${d.realTime.temp}°C\n`;
               systemInstruction += `- Humidity: ${d.realTime.humidity}%\n`;
               systemInstruction += `- Rain (current hour): ${d.realTime.rain}mm\n`;
               systemInstruction += `- Cloud Cover: ${d.realTime.cloudCover}%\n`;
               systemInstruction += `- Wind Speed: ${d.realTime.windSpeed} km/h\n`;
               systemInstruction += `- Delta-T: ${d.realTime.deltaT} (optimal spray range: 2-8)\n`;
               systemInstruction += `- VPD: ${d.realTime.vpd} kPa\n`;
               systemInstruction += `- Dew Point: ${d.realTime.dewPoint}°C\n`;
               systemInstruction += `- ETo (daily): ${d.realTime.et0} mm\n`;
               systemInstruction += `- Leaf Wetness: ${d.realTime.leafWetness}%\n`;
               systemInstruction += `- UV Index: ${d.realTime.uvIndex}\n`;
               systemInstruction += `- Solar Radiation: ${d.realTime.solarRad} W/m²\n`;
               systemInstruction += `- Soil Surface Temp: ${d.realTime.soilTemp}°C\n`;
               systemInstruction += `- Soil Deep Temp (54cm): ${d.realTime.soilTemp54}°C\n`;
               systemInstruction += `- Pressure: ${d.realTime.pressure} hPa\n`;
               systemInstruction += `- Freezing Level: ${d.realTime.freezingLevel}m\n`;
           }
           
           // SOIL PHYSICS & CHEMISTRY
           if (d.soil) {
               systemInstruction += `\n**SOIL PROFILE (0-30cm):**\n`;
               systemInstruction += `- Texture Class: ${d.soil.textureClass}\n`;
               systemInstruction += `- Composition: Clay ${d.soil.clay}%, Sand ${d.soil.sand}%, Silt ${d.soil.silt}%\n`;
               systemInstruction += `- pH: ${d.soil.ph}\n`;
               systemInstruction += `- Nitrogen: ${d.soil.nitrogen} g/kg\n`;
               systemInstruction += `- CEC: ${d.soil.cec} cmol/kg\n`;
               systemInstruction += `- Bulk Density: ${d.soil.bulkDensity} kg/dm³\n`;
               systemInstruction += `- Organic Carbon Stock: ${d.soil.ocs} t/ha\n`;
               systemInstruction += `- Organic Carbon Density: ${d.soil.ocd} kg/dm³\n`;
               systemInstruction += `- Coarse Fragments: ${d.soil.cfvo}%\n`;
               systemInstruction += `- Available Water Capacity (AWC): ${d.soil.awc}%\n`;
               systemInstruction += `- Field Capacity (0.33 bar): ${d.soil.wv0033}% VWC\n`;
               systemInstruction += `- Permanent Wilting Point: ${d.soil.wv1500}% VWC\n`;
               systemInstruction += `- C:N Ratio: ${d.soil.cnRatio}\n`;
               systemInstruction += `- Clay Mineralogy: ${d.soil.mineralogyClass}\n`;
               systemInstruction += `- Phosphorus Availability: ${d.soil.phosphorusIndex}\n`;
               systemInstruction += `- Potassium Potential: ${d.soil.potassiumIndex}\n`;
           }
           
           // WATER & IRRIGATION
           if (d.water) {
               systemInstruction += `\n**WATER & IRRIGATION:**\n`;
               systemInstruction += `- Annual Rainfall (NASA): ${d.water.annualRainfall} mm\n`;
               systemInstruction += `- Drought Stress Index: ${d.water.stressIndex}/10\n`;
               systemInstruction += `- Water Scarcity Class: ${d.water.scarcityClass}\n`;
               systemInstruction += `- Irrigation Efficiency Potential: ${d.water.irrigationEfficiencyPotential}%\n`;
           }
           
           // AGRO-CLIMATE
           if (d.climate) {
               systemInstruction += `\n**AGRO-CLIMATE:**\n`;
               systemInstruction += `- Growing Degree Days (GDD): ${d.climate.growingDegreeDays}\n`;
               systemInstruction += `- Aridity Index: ${d.climate.aridityIndex}\n`;
               systemInstruction += `- Drought Risk: ${d.climate.droughtRisk}\n`;
               systemInstruction += `- Erosion Risk: ${d.climate.erosionRisk}\n`;
           }
           
           // LAND SUITABILITY
           if (d.landSuitability) {
               systemInstruction += `\n**LAND SUITABILITY (GAEZ Analysis):**\n`;
               systemInstruction += `- Suitability Score: ${d.landSuitability.gaezScore}/100\n`;
               systemInstruction += `- Suitability Class: ${d.landSuitability.suitabilityClass}\n`;
               systemInstruction += `- Potential Yield (Rainfed): ${d.landSuitability.potentialYield} t/ha\n`;
               systemInstruction += `- Attainable Yield (Irrigated): ${d.landSuitability.attainableYield} t/ha\n`;
               if (d.landSuitability.limitingFactors?.length) {
                   systemInstruction += `- Limiting Factors: ${d.landSuitability.limitingFactors.join(', ')}\n`;
               }
           }
        }
    }

    // 3. AI ORGANISM ORCHESTRATION
    // Call specialized AIs based on query intent, then LLM synthesizes results
    let aiOrganismResults: { detected_intents: string[]; ai_results: Record<string, unknown>; routed_to: string[] } | null = null;
    
    if (USE_PYTHON_BACKEND) {
        try {
            console.log("🧠 Calling AI Organism Orchestrator...");
            console.log("   Context available:", !!context, "Data available:", !!context?.data);
            
            // Build context for orchestrator - use full context.data if available
            const orchestratorContext = context?.data || {
                realTime: { temp: 20, humidity: 50 }, // Fallback minimal context
            };
            
            const orchestrateRes = await fetch(`${PYTHON_API_URL}/orchestrate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query: message,
                    context: orchestratorContext,
                    crop: context?.cropCode || "tomato"
                })
            });
            
            console.log("   Orchestrator response status:", orchestrateRes.status);
            
            if (orchestrateRes.ok) {
                aiOrganismResults = await orchestrateRes.json();
                console.log("✅ AI Organism responded:", aiOrganismResults?.detected_intents);
                console.log("   Routed to:", aiOrganismResults?.routed_to);
                
                // Inject AI results into system prompt
                if (aiOrganismResults && Object.keys(aiOrganismResults.ai_results).length > 0) {
                    systemInstruction += `\n\n**SPECIALIZED AI ANALYSIS:**\n`;
                    systemInstruction += `(These are results from specialized deep learning modules. Use them to inform your response.)\n\n`;
                    
                    for (const [aiName, result] of Object.entries(aiOrganismResults.ai_results)) {
                        systemInstruction += `### ${aiName.replace(/_/g, ' ').toUpperCase()}:\n`;
                        systemInstruction += `\`\`\`json\n${JSON.stringify(result, null, 2)}\n\`\`\`\n\n`;
                    }
                    
                    systemInstruction += `\n**INSTRUCTION:** Synthesize the above AI analysis into a clear, actionable response. `;
                    systemInstruction += `Explain the findings in natural language. If there are recommendations, prioritize them. `;
                    systemInstruction += `Do NOT just dump the JSON - explain what it means for the farmer.\n`;
                }
            } else {
                const errorText = await orchestrateRes.text();
                console.warn("⚠️ AI Organism Orchestrator returned non-OK status:", orchestrateRes.status, errorText);
            }
        } catch (e) {
            console.warn("⚠️ Could not reach AI Organism (Python backend):", e);
        }
    }

    // 4. Build Message History (include previous messages if provided)
    const messages: any[] = [
        { role: "system", content: systemInstruction }
    ];
    
    // Add conversation history if provided
    if (history && Array.isArray(history)) {
        for (const msg of history) {
            messages.push({ role: msg.role, content: msg.content });
        }
    } else {
        // No history, just add current message
        messages.push({ role: "user", content: message });
    }

    console.log("📤 Sending request to OpenRouter (LLM Conductor)...");
    const initialCompletion = await chatCompletion(messages, tools);
    const choice = initialCompletion.choices[0];
    const assistantMessage = choice.message;

    // 4. Handle Tool Calls
    if (assistantMessage.tool_calls && assistantMessage.tool_calls.length > 0) {
        console.log(`🔧 OpenRouter requested ${assistantMessage.tool_calls.length} tool calls`);
        
        // Append the assistant's request to history
        messages.push(assistantMessage);

        for (const toolCall of assistantMessage.tool_calls) {
            const fnName = toolCall.function.name;
            const fnArgs = JSON.parse(toolCall.function.arguments);
            
            console.log(`🤖 Tool Call: ${fnName}`, fnArgs);

            let toolResult;
            if (toolsMap[fnName]) {
                toolResult = await toolsMap[fnName](fnArgs);
                console.log(`✅ Tool ${fnName} executed`);
            } else {
                console.warn(`⚠️ Tool ${fnName} not found`);
                toolResult = { error: "Tool not found" };
            }

            // Append tool result to history
            messages.push({
                role: "tool",
                tool_call_id: toolCall.id,
                name: fnName,
                content: JSON.stringify(toolResult)
            });
        }

        // 5. Final Completion after Tools
        console.log("📤 Sending tool outputs back to OpenRouter...");
        const finalCompletion = await chatCompletion(messages, tools);
        const finalText = finalCompletion.choices[0].message.content;
        console.log("🤖 Final Response:", finalText);

        return NextResponse.json({ 
            text: finalText || "I processed the tools but have no further comments.",
            toolCalls: assistantMessage.tool_calls.map((tc: any, i: number) => ({ 
                name: tc.function.name, 
                args: JSON.parse(tc.function.arguments),
                // We map the result from our history. 
                // The history has: [system, user, assistant(calls), tool(result1), tool(result2), assistant(final)]
                // So the tool result corresponds to the message with tool_call_id matching tc.id
                result: (() => {
                    const toolMsg = messages.find(m => m.role === 'tool' && m.tool_call_id === tc.id);
                    return toolMsg ? JSON.parse(toolMsg.content) : null;
                })()
            })) 
        });

    } else {
        // No structured tool call found. 
        // CHECK FOR HALLUCINATED JSON TOOL CALL (Gemma 3 Fallback)
        const text = assistantMessage.content;
        let manualToolCall = null;
        
        try {
            // regex to extract JSON block
            const jsonMatch = text.match(/```json\s*([\s\S]*?)\s*```/) || text.match(/\{[\s\S]*"tool"[\s\S]*\}/);
            if (jsonMatch) {
                const jsonStr = jsonMatch[1] || jsonMatch[0];
                const parsed = JSON.parse(jsonStr);
                if (parsed.tool && toolsMap[parsed.tool]) {
                    console.log(`🕵️ Detected Manual JSON Tool Call: ${parsed.tool}`);
                    manualToolCall = {
                        id: "manual_" + Date.now(),
                        function: {
                            name: parsed.tool,
                            arguments: JSON.stringify(parsed) // or parsed.parameters ??
                        }
                    };
                    
                    // Normalize arguments: The model might put args in top-level or 'parameters' key
                    // Our tools expect specific keys.
                    // ml_predictYield expects { fieldId, crop }. 
                    // Model gave: { tool, crop, coordinates, ... }
                    // We need to map this carefully or just pass the whole object if flexible.
                    // Let's pass 'parsed' as args, assuming Pydantic/Zod strips extras or we accept broad inputs.
                    // Wait, our Zod schema is strict.
                    // Let's map "crop" -> "crop". "coordinates" is extraneous but okay?
                    // Let's use `parsed.parameters` if it exists, else `parsed`.
                    manualToolCall.function.arguments = JSON.stringify(parsed.parameters || parsed);
                }
            }
        } catch (e) {
            // Not JSON or failed to parse
        }

        if (manualToolCall) {
            // EXECUTE MANUALLY
             console.log(`🤖 Executing Manual Tool: ${manualToolCall.function.name}`);
             const fnName = manualToolCall.function.name;
             const fnArgs = JSON.parse(manualToolCall.function.arguments);
             
             let toolResult;
             if (toolsMap[fnName]) {
                  // Normalize arguments for EO tool (add defaults if AI omitted them)
                  if (fnName === 'eo_getFieldIndicators') {
                      fnArgs.fieldId = fnArgs.fieldId || 'default-field';
                      fnArgs.startDate = fnArgs.startDate || new Date(Date.now() - 30*24*60*60*1000).toISOString().split('T')[0];
                      fnArgs.endDate = fnArgs.endDate || new Date().toISOString().split('T')[0];
                      fnArgs.indicators = fnArgs.indicators || ['ndvi', 'ndmi'];
                  }
                  // Normalize arguments for ML tool
                  if (fnName === 'ml_predictYield') {
                      fnArgs.fieldId = fnArgs.fieldId || 'default-field';
                      fnArgs.crop = fnArgs.crop || 'tomato';
                  }
                  
                  toolResult = await toolsMap[fnName](fnArgs);
                  console.log(`✅ Manual Tool ${fnName} executed`);
             } else {
                 toolResult = { error: "Tool not found" };
             }
             
             // Return formatted response mimicking a real tool call
             return NextResponse.json({ 
                text: "I analyzed the data.", // Simplified text response
                toolCalls: [{
                    name: fnName,
                    args: fnArgs,
                    result: toolResult
                }]
             });
        }

        console.log("🤖 Response (No Tool):", text);
        return NextResponse.json({ text });
    }

  } catch (error) {
    console.error("💥 AgriBrain Chat Error:", error);
    return NextResponse.json(
      { error: "Failed to process request", details: String(error) },
      { status: 500 }
    );
  }
}
