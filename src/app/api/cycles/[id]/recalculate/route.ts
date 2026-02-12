
import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { ObjectId } from "bson";
import { generateAICropPlan, AIStage } from "@/lib/agribrain/gemini-advisor";
import { getFAOLandIntelligence } from "@/lib/agribrain/fao-data-service";
import wilayasData from "@/data/algeria/wilayas.json";

const VALID_TASK_TYPES = [
  "PLANTING", "IRRIGATION", "FERTILIZING", 
  "PEST_CONTROL", "PRUNING", "WEEDING", 
  "HARVEST", "SOIL_PREP", "OTHER"
];

export async function POST(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: cycleId } = await params;
    
    if (!ObjectId.isValid(cycleId)) {
        return NextResponse.json({ error: "Invalid Cycle ID" }, { status: 400 });
    }

    // 1. Fetch Cycle with Relations
    // 1. Fetch Cycle (without robust includes first to avoid crash)
    let cycle = await prisma.cropCycle.findFirst({
        where: { id: cycleId },
        include: { tasks: true } // Tasks are usually safe
    });

    if (!cycle) {
        // Fallback: try finding in all cycles
        const allCycles = await prisma.cropCycle.findMany({ include: { tasks: true } });
        cycle = allCycles.find(c => c.id === cycleId) || null;
    }

    if (!cycle) {
        return NextResponse.json({ error: "Cycle not found" }, { status: 404 });
    }

    // 2. Fetch Plot Manually (Robust)
    let plot = await prisma.plot.findFirst({
        where: { id: cycle.plotId },
        include: { farm: true }
    });

    if (!plot) {
        console.log(`[SmartUpdate] Direct plot lookup failed for ${cycle.plotId}, trying fallback...`);
        const allPlots = await prisma.plot.findMany();
        const foundPlot = allPlots.find(p => p.id === cycle.plotId);
        
        if (foundPlot) {
            const relatedFarm = await prisma.farm.findUnique({ where: { id: foundPlot.farmId } });
            plot = { ...foundPlot, farm: relatedFarm } as any;
        }
    }

    // Mock plot if absolutely missing (to allow recalculation based on generic defaults)
    const safePlot = plot || { 
        area: 1, 
        soilType: "LOAM", 
        irrigation: "RAINFED", 
        farm: { wilaya: "Algeria", latitude: 36.75, longitude: 3.05 } 
    } as any;

    // 3. Calculate Progress
    const plantDate = new Date(cycle.plantDate);
    const now = new Date();
    const daysElapsed = Math.max(0, Math.ceil((now.getTime() - plantDate.getTime()) / (1000 * 60 * 60 * 24)));

    // 4. Fetch Intelligent Context
    const cropName = cycle.cropNameAr || cycle.cropCode;
    let faoProfile = undefined;
    
    if (safePlot.farm?.latitude && safePlot.farm?.longitude) {
        try {
             console.log(`[SmartUpdate] Fetching FAO Data for ${cropName}...`);
             faoProfile = await getFAOLandIntelligence(safePlot.farm.latitude, safePlot.farm.longitude, cropName);
        } catch (e) {
             console.warn("FAO Fetch failed during update", e);
        }
    }

    // 5. Generate NEW Plan
    const wilayaName = safePlot.farm?.wilaya || "Algeria";
    const wilayaInfo = wilayasData.wilayas.find(w => w.nameAr === wilayaName || w.nameEn === wilayaName);

    console.log(`[SmartUpdate] Generating AI Plan for day ${daysElapsed}+`);
    
    let aiPlan: AIStage[] = [];
    try {
        aiPlan = await generateAICropPlan(cropName, {
            wilayaName: wilayaName,
            wilayaCode: wilayaInfo?.code || "16",
            soilType: safePlot.soilType || "General",
            irrigationType: safePlot.irrigation || "General",
            plotArea: safePlot.area,
            growthStage: daysElapsed < 20 ? "Emergence" : daysElapsed < 60 ? "Vegetative" : "Reproductive"
        }, faoProfile);
    } catch (e) {
        return NextResponse.json({ error: "AI Generation Failed", details: String(e) }, { status: 500 });
    }

    if (!aiPlan || aiPlan.length === 0) {
        return NextResponse.json({ error: "AI returned empty plan" }, { status: 500 });
    }

    // 5. Reconcile Tasks
    // A. Delete PENDING tasks that are in the future
    const pendingTasks = await prisma.cropTask.findMany({
        where: {
            cropCycleId: cycleId,
            completed: false,
            dueDate: { gt: now }
        },
        select: { id: true }
    });

    if (pendingTasks.length > 0) {
        console.log(`[SmartUpdate] Removing ${pendingTasks.length} old future tasks via Raw Command...`);
        // Use Raw Command to bypass potential Replica Set issues with deleteMany
        try {
            const taskIds = pendingTasks.map(t => ({ "$oid": t.id }));
            await prisma.$runCommandRaw({
                delete: "CropTask",
                deletes: [
                    { q: { _id: { "$in": taskIds } }, limit: 0 } // limit 0 = delete all matching
                ]
            });
        } catch (rawDeleteError) {
             console.error("Raw Delete Failed, trying standard deleteMany fallback...", rawDeleteError);
             await prisma.cropTask.deleteMany({
                where: { id: { in: pendingTasks.map(t => t.id) } }
             });
        }
    }

    // B. Create NEW tasks from the AI plan (only those strictly in the future)
    const tasksToCreate = [];
    
    for (const stage of aiPlan) {
        if (stage.tasks) {
            for (const task of stage.tasks) {
                // Calculate absolute due date
                const dueDate = new Date(plantDate);
                dueDate.setDate(plantDate.getDate() + task.dayOffset);

                // Only add if it's in the future relative to the "Recalculation Horizon" (today)
                if (dueDate > now) {
                     // Sanitize type
                    let taskType = task.type.toUpperCase();
                    if (!VALID_TASK_TYPES.includes(taskType)) {
                        if (taskType.includes("WATER") || taskType.includes("IRRIG")) taskType = "IRRIGATION";
                        else if (taskType.includes("FERT")) taskType = "FERTILIZING";
                        else if (taskType.includes("PEST")) taskType = "PEST_CONTROL";
                        else if (taskType.includes("PLANT") || taskType.includes("SOW")) taskType = "PLANTING";
                        else taskType = "OTHER";
                    }

                    tasksToCreate.push({
                        _id: { "$oid": new ObjectId().toString() },
                        cropCycleId: { "$oid": cycleId },
                        type: taskType,
                        title: task.title,
                        titleAr: task.titleAr || task.title,
                        description: task.descriptionAr || `Updated by Smart Engine`,
                        dueDate: { "$date": dueDate.toISOString() },
                        completed: false,
                        createdAt: { "$date": new Date().toISOString() },
                        updatedAt: { "$date": new Date().toISOString() }
                    });
                }
            }
        }
    }

    // Insert new tasks
    if (tasksToCreate.length > 0) {
        console.log(`[SmartUpdate] Inserting ${tasksToCreate.length} new optimized tasks...`);
        for (const taskDoc of tasksToCreate) {
             await prisma.$runCommandRaw({
                insert: "CropTask",
                documents: [taskDoc]
            });
        }
    }

    return NextResponse.json({ 
        success: true, 
        message: `Plan updated. Removed ${pendingTasks.length} old tasks, added ${tasksToCreate.length} new smart tasks.`
    });

  } catch (error) {
    console.error("Smart Update Error:", error);
    return NextResponse.json({ error: "Smart Update Failed", details: String(error) }, { status: 500 });
  }
}
