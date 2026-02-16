import { NextResponse } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';
import { prisma } from '@/lib/db';

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { plotId, config } = body;

    if (!plotId) {
      return NextResponse.json({ error: 'Missing plotId' }, { status: 400 });
    }

    // 1. Fetch Real Data from DB
    const plot = await prisma.plot.findUnique({
      where: { id: plotId },
      include: {
        farm: true,
        cropCycles: {
          where: { status: { not: 'HARVESTED' } },
          orderBy: { plantDate: 'desc' },
          take: 1
        },
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

    // 2. Prepare Context
    const injectedContext: any = {};
    
    if (plot) {
        // Location
        injectedContext.lat = plot.farm?.latitude || 36.0; 
        injectedContext.lng = plot.farm?.longitude || 3.0;
        injectedContext.area = plot.area;

        // Crop Info
        if (plot.cropCycles && plot.cropCycles.length > 0) {
            injectedContext.crop = plot.cropCycles[0].cropCode;
            injectedContext.stage = plot.cropCycles[0].status;
        }

        // Soil Data
        if (plot.soilAnalyses && plot.soilAnalyses.length > 0) {
            const soil = plot.soilAnalyses[0];
            injectedContext.soil = {
                type: plot.soilType || "LOAM", // Fallback to plot-level type
                ph: soil.ph,
                organic_matter: soil.organicMatter,
                texture: soil.texture
            };
        }

        // Sensor Data (aggregating latest readings)
        if (plot.sensors && plot.sensors.length > 0) {
            const sensorData: any = {};
            plot.sensors.forEach(s => {
                if (s.readings.length > 0) {
                    const r = s.readings[0];
                    // Map available readings
                    if (r.soilMoisture !== null) sensorData.soil_moisture = r.soilMoisture;
                    if (r.temperature !== null) sensorData.temperature = r.temperature;
                    if (r.humidity !== null) sensorData.humidity = r.humidity;
                    if (r.rainfall !== null) sensorData.rainfall = r.rainfall;
                }
            });
            injectedContext.sensors = sensorData;
        }
    }

    // Path to Orchestrator
    const scriptPath = path.join(process.cwd(), 'services', 'agribrain', 'orchestrator.py');
    
    // Spawn Python Process
    // Fixed: Using 'py' for Windows environment.
    const pythonProcess = spawn('py', [
      scriptPath,
      '--plot_id', plotId,
      '--config', JSON.stringify(config || {}),
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
        console.error(`[AgriBrain Python] ${data}`); // Log logs
      });

      pythonProcess.on('close', (code) => {
        if (code === 0) {
          resolve(dataString);
        } else {
          reject(new Error(`Process exited with code ${code}: ${errorString}`));
        }
      });
    });

    try {
      await processPromise;
      // Parse JSON output from Python
      const analysisResult = JSON.parse(dataString);
      return NextResponse.json(analysisResult);
      
    } catch (err: any) {
      console.error("Orchestrator Failed:", err);
      // Fallback/Mock for Dev if Python fails (e.g., missing deps)
      return NextResponse.json({ 
        error: 'Engine Execution Failed', 
        details: err.message,
        fallback: true 
      }, { status: 500 });
    }

  } catch (error) {
    return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 });
  }
}
