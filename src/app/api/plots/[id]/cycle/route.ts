
import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { ObjectId } from "bson";
import { generateAICropPlan, AIStage } from "@/lib/agribrain/gemini-advisor";
import { getFAOLandIntelligence } from "@/lib/agribrain/fao-data-service";
import wilayasData from "@/data/algeria/wilayas.json";

// Keep this in sync with schema.prisma
const VALID_TASK_TYPES = [
  "PLANTING", "IRRIGATION", "FERTILIZING", 
  "PEST_CONTROL", "PRUNING", "WEEDING", 
  "HARVEST", "SOIL_PREP", "OTHER"
];

// POST /api/plots/[id]/cycle - Start a new crop cycle
export async function POST(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: plotId } = await params;
    
    if (!ObjectId.isValid(plotId)) {
        return NextResponse.json({ error: "Invalid Plot ID" }, { status: 400 });
    }

    const body = await req.json();
    const { 
        cropName, 
        variety, 
        startDate,
        soilType,
        irrigationType
    } = body;

    if (!cropName || !startDate) {
      return NextResponse.json(
        { error: "Missing required fields: cropName, startDate" }, 
        { status: 400 }
      );
    }

    // 1. Fetch Plot and Farm info with Robust Lookup
    let plot = await prisma.plot.findFirst({
        where: { id: plotId },
        include: { farm: true }
    });

    if (!plot) {
        console.log(`[API] Plot direct lookup failed for ${plotId}, trying fallback...`);
        // Fallback: Fetch all plots WITHOUT include to avoid crashing on orphaned data
        const allPlots = await prisma.plot.findMany();
        const foundPlot = allPlots.find(p => p.id === plotId);
        
        if (foundPlot) {
            // Now fetch the farm for this specific plot
            const relatedFarm = await prisma.farm.findUnique({
                where: { id: foundPlot.farmId }
            });
            
            // Allow plot to exist even if farm is missing (orphaned)
            // matching the Page behavior which renders fine even if farm is missing
            plot = {
                ...foundPlot,
                farm: relatedFarm || { wilaya: "Algeria", wilayaCode: "16" } // Default context if orphaned
            } as any;
        }
    }

    if (!plot) {
        return NextResponse.json({ error: `Plot not found for ID: ${plotId}` }, { status: 404 });
    }

    // 2. Generate Plan via AI
    const wilayaName = plot.farm?.wilaya || "Algeria";
    const wilayaInfo = wilayasData.wilayas.find(w => w.nameAr === wilayaName || w.nameEn === wilayaName);
    
    // Fetch Intelligent Context (Soil/Weather)
    let faoProfile = undefined;
    if (plot.farm?.latitude && plot.farm?.longitude) {
        try {
             console.log(`Fetching FAO Intelligence for Smart Cycle Optimization...`);
             faoProfile = await getFAOLandIntelligence(plot.farm.latitude, plot.farm.longitude, cropName);
        } catch (faoError) {
             console.warn("Failed to fetch FAO data for cycle generation, proceeding with basic context.", faoError);
        }
    }

    let aiPlan: AIStage[] = [];
    try {
        console.log(`Generating AI plan for ${cropName} in ${wilayaName} with Smart Context...`);
        aiPlan = await generateAICropPlan(cropName, {
            wilayaName: wilayaName,
            wilayaCode: wilayaInfo?.code || "16",
            soilType: soilType || plot.soilType || "General",
            irrigationType: irrigationType || plot.irrigation || "General",
            plotArea: plot.area
        }, faoProfile); // Pass the profile here
    } catch (error) {
        console.error("AI Plan Generation failed, using fallback:", error);
    }

    // Force fallback if AI returned empty plan or failed silently
    if (!aiPlan || aiPlan.length === 0) {
        console.log("AI Plan was empty, using fallback default.");
        aiPlan = [{
            stageName: "Growth",
            stageNameAr: "مرحلة النمو",
            startDay: 0,
            endDay: 90,
            tasks: [
                { title: "Planting", titleAr: "الزراعة", dayOffset: 0, type: "PLANTING" },
                { title: "Irrigation", titleAr: "الري المنتظم", dayOffset: 2, type: "IRRIGATION" },
                { title: "Fertilizing", titleAr: "تسميد", dayOffset: 15, type: "FERTILIZING" },
                { title: "Harvest", titleAr: "الحصاد", dayOffset: 90, type: "HARVEST" }
            ]
        }];
    }

    // 3. Create CropCycle using Raw Command to bypass Prisma "Replica Set" check
    const maxDay = Math.max(...aiPlan.map(s => s.endDay), 90);
    const start = new Date(startDate);
    const expectedHarvest = new Date(start);
    expectedHarvest.setDate(start.getDate() + maxDay);

    const cycleId = new ObjectId().toString();
    const now = new Date();

    try {
        console.log("Attempting raw insert for CropCycle...");
        await prisma.$runCommandRaw({
            insert: "CropCycle",
            documents: [{
                _id: { "$oid": cycleId },
                plotId: { "$oid": plotId },
                cropCode: cropName.toLowerCase().replace(/\s+/g, '_'),
                cropNameAr: cropName,
                variety: variety || null,
                status: "PLANTED",
                plantDate: { "$date": start.toISOString() },
                expectedHarvest: { "$date": expectedHarvest.toISOString() },
                notes: `Generated by AgriBrain AI for ${cropName}`,
                createdAt: { "$date": now.toISOString() },
                updatedAt: { "$date": now.toISOString() }
            }]
        });
        console.log("Raw insert successful");
    } catch (rawError) {
        console.error("Raw insert failed:", rawError);
        throw rawError;
    }

    // Mock object for downstream logic
    const cycle = { id: cycleId };

    // 4. Create Tasks based on Plan (Sanitized)
    const tasksToCreate = [];
    
    for (const stage of aiPlan) {
        if (stage.tasks) {
            for (const task of stage.tasks) {
                const dueDate = new Date(start);
                dueDate.setDate(start.getDate() + task.dayOffset);
                
                // Sanitize type
                let taskType = task.type.toUpperCase();
                if (!VALID_TASK_TYPES.includes(taskType)) {
                    // Try mapping or fallback
                    if (taskType.includes("WATER") || taskType.includes("IRRIG")) taskType = "IRRIGATION";
                    else if (taskType.includes("FERT")) taskType = "FERTILIZING";
                    else if (taskType.includes("PEST")) taskType = "PEST_CONTROL";
                    else if (taskType.includes("PLANT") || taskType.includes("SOW")) taskType = "PLANTING";
                    else taskType = "OTHER";
                }

                tasksToCreate.push({
                    cropCycleId: cycle.id,
                    type: taskType as any,
                    title: task.title,
                    titleAr: task.titleAr,
                    description: task.descriptionAr || `مهمة خاصة بـ ${stage.stageNameAr}`,
                    dueDate: dueDate,
                    completed: false
                });
            }
        }
    }

    // Write diagnostics to file
    try {
        const fs = require('fs');
        const path = require('path');
        const logPath = path.join(process.cwd(), 'debug_log.txt');
        const logMsg = `\n[${new Date().toISOString()}] Cycle Created: ${cycleId}\nPlan Stages: ${aiPlan.length}\nTasks to create: ${tasksToCreate.length}\n`;
        fs.appendFileSync(logPath, logMsg);
    } catch (e) {}

    if (tasksToCreate.length > 0) {
        console.log("Creating tasks individually to avoid Replica Set requirement...");
        const cycleObjectId = { "$oid": cycleId }; // Reuse the ID we generated for the cycle
        
        for (const task of tasksToCreate) {
            try {
                // Manually map fields to BSON format
                const taskId = new ObjectId().toString();
                const taskDoc = {
                    _id: { "$oid": taskId },
                    cropCycleId: cycleObjectId, // Link to the cycle we just created raw
                    type: task.type,
                    title: task.title,
                    titleAr: task.titleAr || "",
                    description: task.description || "",
                    dueDate: { "$date": new Date(task.dueDate).toISOString() },
                    completed: false,
                    createdAt: { "$date": new Date().toISOString() },
                    updatedAt: { "$date": new Date().toISOString() }
                };

                await prisma.$runCommandRaw({
                    insert: "CropTask",
                    documents: [taskDoc]
                });
            } catch (taskErr) {
               console.error("Failed to create individual task:", taskErr);
               try {
                    const fs = require('fs');
                    const path = require('path');
                    const logPath = path.join(process.cwd(), 'debug_log.txt');
                    fs.appendFileSync(logPath, `[Task Raw Error] ${task.title}: ${String(taskErr)}\n`);
               } catch (e) {}
            }
        }
    }

    return NextResponse.json({ 
        success: true, 
        cycleId: cycle.id,
        message: "تم إنشاء الدورة الزراعية بنجاح" 
    });

  } catch (error) {
    console.error("Error creating cycle (Detailed):", error);
    
    // Write error to file for debugging
    try {
        const fs = require('fs');
        const path = require('path');
        const logPath = path.join(process.cwd(), 'debug_log.txt');
        const errorLog = `\n[${new Date().toISOString()}] Error: ${String(error)}\nStack: ${error instanceof Error ? error.stack : 'No stack'}\n`;
        fs.appendFileSync(logPath, errorLog);
    } catch (fsError) {
        console.error("Failed to write log file:", fsError);
    }

    return NextResponse.json(
      { error: "Error creating cycle", details: String(error) }, 
      { status: 500 }
    );
  }
}
