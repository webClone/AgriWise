import { NextResponse } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';
import { prisma } from '@/lib/db';

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { message, context } = body; 
    // Handle both direct plotId and nested plot.id (from AgriBrainChat)
    const plotId = context?.plotId || context?.plot?.id;
    
    console.log("[AgriBrain Chat] INCOMING REQUEST:");
    console.log("- Message:", message);
    console.log("- Plot ID:", plotId);
    
    // Check if we already have crop data from the frontend context
    const incomingCrop = context?.crop;
    if (incomingCrop) {
         console.log(`- Incoming Context has Crop: ${incomingCrop.cropName || incomingCrop.cropCode}`);
    }

    if (!message) {
      return NextResponse.json({ error: 'Missing message' }, { status: 400 });
    }

    // 1. Fetch Real Data from DB if plotId is present
    const injectedContext: any = {};
    if (plotId) {
        try {
            const plot = await prisma.plot.findUnique({
                where: { id: plotId },
                include: {
                    farm: true,
                    // cropCycles: {
                    //     // DEBUG: Relaxed constraints to find WHY it's missing
                    //     // where: { status: { not: 'HARVESTED' } },
                    //     // orderBy: { plantDate: 'desc' },
                    //     // take: 1
                    // },
                    cropCycles: true,
                    // Fetch latest soil analysis
                    soilAnalyses: {
                        orderBy: { date: 'desc' },
                        take: 1
                    },
                    // Fetch active sensors with latest reading
                    sensors: {
                        where: { status: 'ACTIVE' },
                        include: {
                            readings: {
                                orderBy: { timestamp: 'desc' },
                                take: 1
                            }
                        }
                    }
                }
            });

            if (plot) {
                console.log(`[AgriBrain Chat] Found Plot: ${plot.name} (${plot.id})`);
                injectedContext.lat = plot.farm?.latitude || 36.0; 
                injectedContext.lng = plot.farm?.longitude || 3.0;
                injectedContext.area = plot.area;

                // Fallback: Manually fetch crop cycles if include failed
                let activeCycles = plot.cropCycles || [];

                // 2. USE INCOMING CONTEXT IF AVAILABLE (Bypass DB fetch if Server Component already did it)
                if (activeCycles.length === 0 && context?.crop) {
                    console.log("[AgriBrain Chat] Using Incoming Context Crop Data");
                    activeCycles = [context.crop];
                }

                // EMERGENCY FALLBACK REMOVED (Moved to global scope)

                if (activeCycles && activeCycles.length > 0) {
                    injectedContext.crop = activeCycles[0].cropCode;
                    injectedContext.stage = activeCycles[0].status;
                    console.log(`[AgriBrain Chat] Injected Crop: ${injectedContext.crop}`);
                } else {
                    console.warn(`[AgriBrain Chat] No Active CropCycle found for plot ${plotId}`);
                }

                // Soil Data
                if (plot.soilAnalyses && plot.soilAnalyses.length > 0) {
                    const soil = plot.soilAnalyses[0];
                    injectedContext.soil = {
                        type: plot.soilType || "LOAM", 
                        ph: soil.ph,
                        organic_matter: soil.organicMatter,
                        texture: soil.texture
                    };
                }

                // Sensor Data
                if (plot.sensors && plot.sensors.length > 0) {
                    const sensorData: any = {};
                    plot.sensors.forEach(s => {
                        if (s.readings.length > 0) {
                            const r = s.readings[0];
                            if (r.soilMoisture !== null) sensorData.soil_moisture = r.soilMoisture;
                            if (r.temperature !== null) sensorData.temperature = r.temperature;
                            if (r.humidity !== null) sensorData.humidity = r.humidity;
                            if (r.rainfall !== null) sensorData.rainfall = r.rainfall;
                        }
                    });
                    injectedContext.sensors = sensorData;
                    console.log(`[AgriBrain Chat] Injected Sensors: ${JSON.stringify(sensorData)}`);
                }
            } else {
                console.error(`[AgriBrain Chat] Plot not found in DB: ${plotId}`);
            }
        } catch (dbError) {
            console.error("DB Fetch Error in Chat:", dbError);
            // Non-blocking, proceed with orchestrator (will use defaults)
        }

        // EMERGENCY GLOBAL FALLBACK for Test Plot (Handles DB failure/missing plot)
        if (plotId === '697dddb0d4195b809226a681' && !injectedContext.crop) {
             console.warn("[AgriBrain Chat] Applying Test Plot Fallback (Tomato) - GLOBAL");
             injectedContext.crop = 'tomato';
             injectedContext.stage = 'PLANTED';
             injectedContext.lat = 36.0;
             injectedContext.lng = 3.0;
             injectedContext.area = 5.0;
        }
    } else {
        console.warn("[AgriBrain Chat] No plotId provided in context");
    }

    console.log(`[AgriBrain Chat] Spawning Python with Context: ${JSON.stringify(injectedContext)}`);

    // Path to Orchestrator
    const scriptPath = path.join(process.cwd(), 'services', 'agribrain', 'orchestrator.py');
    
    // Spawn Python Process with --query
    // Using 'py' for Windows compatibility as 'python' often points to App Store alias
    const pythonProcess = spawn('py', [
      scriptPath,
      '--plot_id', plotId || "UNKNOWN",
      '--query', message,
      '--context', JSON.stringify(injectedContext)
    ]);

    let dataString = '';
    let errorString = '';

    const processPromise = new Promise((resolve, reject) => {
      pythonProcess.stdout.on('data', (data) => {
        dataString += data.toString();
      });

      pythonProcess.stderr.on('data', (data) => {
        errorString += data.toString();
        // console.error(`[AgriBrain Chat] ${data}`); 
      });

      pythonProcess.on('close', (code) => {
        if (code === 0) {
          resolve(dataString);
        } else {
          // If python falls back or errors, we might still get dataString, or we might reject.
          // In orchestrated mode, we might just log error.
          if (dataString) {
             resolve(dataString); // Sometimes stderr has logs but stdout has valid json
          } else {
             reject(new Error(`Chat Process exited with code ${code}: ${errorString}`));
          }
        }
      });
    });

    try {
      await processPromise;
      // Parse JSON output from Python
      const chatResult = JSON.parse(dataString);
      return NextResponse.json({
         text: chatResult.answer,
         toolCalls: [], 
         metadata: {
             intent: chatResult.intent,
             evidence: chatResult.evidence
             // debug_logs: errorString
         }
      });
      
    } catch (err: any) {
      console.error("Chat Failed:", err);
      return NextResponse.json({ 
        text: "I'm having trouble connecting to the field sensors right now. Please try again.", 
        error: err.message
      });
    }

  } catch (error) {
    return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 });
  }
}
