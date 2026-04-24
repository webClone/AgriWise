import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { ObjectId } from "bson";

// Demo data for plots, crops, tasks, and equipment
const plotTemplates = [
  { name: "القطعة الشمالية", nameAr: "القطعة الشمالية", areaPercent: 0.4, soilType: "LOAM", irrigation: "DRIP" },
  { name: "القطعة الجنوبية", nameAr: "القطعة الجنوبية", areaPercent: 0.35, soilType: "CLAY", irrigation: "SPRINKLER" },
  { name: "القطعة الشرقية", nameAr: "القطعة الشرقية", areaPercent: 0.25, soilType: "SANDY", irrigation: "FLOOD" },
];

const cropTemplates = [
  { code: "wheat", nameAr: "قمح صلب", variety: "موريتانيا", daysAgo: 90, status: "GROWING" },
  { code: "potato", nameAr: "بطاطا", variety: "سبونتا", daysAgo: 45, status: "VEGETATIVE" },
  { code: "tomato", nameAr: "طماطم", variety: "ريو غراندي", daysAgo: 60, status: "FLOWERING" },
  { code: "barley", nameAr: "شعير", variety: "صحراوي", daysAgo: 75, status: "GROWING" },
  { code: "onion", nameAr: "بصل", variety: "قلمي", daysAgo: 30, status: "PLANTED" },
];

const taskTemplates = [
  { type: "IRRIGATION", title: "سقي المحصول", titleAr: "سقي المحصول", daysFromNow: 1 },
  { type: "FERTILIZING", title: "تسميد آزوتي", titleAr: "تسميد آزوتي", daysFromNow: 3 },
  { type: "PEST_CONTROL", title: "رش مبيد حشري", titleAr: "رش مبيد حشري", daysFromNow: 7 },
  { type: "WEEDING", title: "إزالة الأعشاب الضارة", titleAr: "إزالة الأعشاب الضارة", daysFromNow: 5 },
  { type: "PRUNING", title: "تقليم النباتات", titleAr: "تقليم النباتات", daysFromNow: 10 },
  { type: "SOIL_PREP", title: "تحضير التربة", titleAr: "تحضير التربة", daysFromNow: -5, completed: true },
  { type: "HARVEST", title: "حصاد المحصول", titleAr: "حصاد المحصول", daysFromNow: 30 },
];

const equipmentTemplates = [
  { name: "جرار زراعي", type: "TRACTOR", condition: "good", quantity: 1 },
  { name: "مضخة مياه", type: "PUMP", condition: "new", quantity: 2 },
  { name: "رشاش مبيدات", type: "SPRAYER", condition: "good", quantity: 1 },
  { name: "محراث", type: "PLOW", condition: "fair", quantity: 1 },
  { name: "شاحنة نقل", type: "TRUCK", condition: "good", quantity: 1 },
];

const inputTemplates = [
  { type: "SEED", name: "بذور قمح", nameAr: "بذور قمح صلب", brand: "محلي", quantity: 150, unit: "kg", cost: 45000 },
  { type: "FERTILIZER", name: "سماد NPK", nameAr: "سماد مركب NPK", brand: "Fertial", quantity: 200, unit: "kg", cost: 25000 },
  { type: "FERTILIZER", name: "يوريا", nameAr: "سماد يوريا 46%", brand: "Fertial", quantity: 100, unit: "kg", cost: 15000 },
  { type: "PESTICIDE", name: "مبيد حشري", nameAr: "مبيد أفوكسزانات", brand: "Syngenta", quantity: 5, unit: "liters", cost: 8000 },
  { type: "WATER", name: "مياه ري", nameAr: "مياه ري", quantity: 5000, unit: "liters", cost: 2000 },
];

export async function POST() {
  try {
    const timestamp = Date.now();
    const dateObj = { $date: { $numberLong: String(timestamp) } };

    // Get existing farms
    const farmsResult = await prisma.$runCommandRaw({
      find: "Farm",
      filter: {},
      limit: 10
    }) as { cursor?: { firstBatch?: Array<{ _id: { $oid?: string } | ObjectId; totalArea?: number; name?: string }> } };

    const farms = farmsResult.cursor?.firstBatch || [];
    
    if (farms.length === 0) {
      return NextResponse.json({
        success: false,
        error: "لا توجد مزارع. قم بإضافة مزارع أولاً باستخدام /api/seed/farms"
      }, { status: 400 });
    }

    let totalPlots = 0;
    let totalCrops = 0;
    let totalTasks = 0;
    let totalEquipment = 0;
    let totalInputs = 0;

    // For each farm, create plots, crops, tasks, and equipment
    for (let farmIndex = 0; farmIndex < farms.length; farmIndex++) {
      const farm = farms[farmIndex];
      const farmId = (farm._id as { $oid?: string }).$oid ? new ObjectId((farm._id as { $oid?: string }).$oid!) : farm._id as ObjectId;
      const farmArea = farm.totalArea || 10;

      // Create 2-3 plots per farm
      const numPlots = Math.min(2 + (farmIndex % 2), 3);
      const createdPlotIds: ObjectId[] = [];

      for (let i = 0; i < numPlots; i++) {
        const plotTemplate = plotTemplates[i % plotTemplates.length];
        const plotId = new ObjectId();
        const plotTimestamp = Date.now() + i;
        const plotDateObj = { $date: { $numberLong: String(plotTimestamp) } };

        await prisma.$runCommandRaw({
          insert: "Plot",
          documents: [{
            _id: { $oid: plotId.toHexString() },
            name: `${plotTemplate.name} ${i + 1}`,
            nameAr: `${plotTemplate.nameAr} ${i + 1}`,
            area: +(farmArea * plotTemplate.areaPercent).toFixed(2),
            soilType: plotTemplate.soilType,
            irrigation: plotTemplate.irrigation,
            farmId: { $oid: farmId.toHexString() },
            createdAt: plotDateObj,
            updatedAt: plotDateObj,
          }]
        });

        createdPlotIds.push(plotId);
        totalPlots++;
      }

      // Create 1-2 crop cycles per plot
      for (let plotIndex = 0; plotIndex < createdPlotIds.length; plotIndex++) {
        const plotId = createdPlotIds[plotIndex];
        const numCrops = 1 + (plotIndex % 2); // 1 or 2 crops

        for (let cropIndex = 0; cropIndex < numCrops; cropIndex++) {
          const cropTemplate = cropTemplates[(farmIndex + plotIndex + cropIndex) % cropTemplates.length];
          const cropCycleId = new ObjectId();
          
          const plantDate = new Date();
          plantDate.setDate(plantDate.getDate() - cropTemplate.daysAgo);
          const expectedHarvest = new Date(plantDate);
          expectedHarvest.setDate(expectedHarvest.getDate() + 120); // ~4 months crop cycle

          const cropTimestamp = Date.now() + plotIndex + cropIndex;
          const cropDateObj = { $date: { $numberLong: String(cropTimestamp) } };

          await prisma.$runCommandRaw({
            insert: "CropCycle",
            documents: [{
              _id: { $oid: cropCycleId.toHexString() },
              cropCode: cropTemplate.code,
              cropNameAr: cropTemplate.nameAr,
              variety: cropTemplate.variety,
              plantDate: { $date: { $numberLong: String(plantDate.getTime()) } },
              expectedHarvest: { $date: { $numberLong: String(expectedHarvest.getTime()) } },
              status: cropTemplate.status,
              estimatedYield: Math.floor(Math.random() * 3000 + 2000), // 2000-5000 kg/ha
              plotId: { $oid: plotId.toHexString() },
              createdAt: cropDateObj,
              updatedAt: cropDateObj,
            }]
          });

          totalCrops++;

          // Create 3-5 tasks per crop cycle
          const numTasks = 3 + Math.floor(Math.random() * 3);
          for (let taskIndex = 0; taskIndex < numTasks; taskIndex++) {
            const taskTemplate = taskTemplates[taskIndex % taskTemplates.length];
            const taskId = new ObjectId();
            
            const dueDate = new Date();
            dueDate.setDate(dueDate.getDate() + taskTemplate.daysFromNow);
            
            const taskTimestamp = Date.now() + taskIndex;
            const taskDateObj = { $date: { $numberLong: String(taskTimestamp) } };

            await prisma.$runCommandRaw({
              insert: "CropTask",
              documents: [{
                _id: { $oid: taskId.toHexString() },
                type: taskTemplate.type,
                title: taskTemplate.title,
                titleAr: taskTemplate.titleAr,
                description: `مهمة ${taskTemplate.titleAr} للمحصول ${cropTemplate.nameAr}`,
                dueDate: { $date: { $numberLong: String(dueDate.getTime()) } },
                completed: taskTemplate.completed || false,
                completedAt: taskTemplate.completed ? taskDateObj : null,
                cropCycleId: { $oid: cropCycleId.toHexString() },
                createdAt: taskDateObj,
              }]
            });

            totalTasks++;
          }

          // Create 2-3 input logs per crop cycle
          const numInputs = 2 + Math.floor(Math.random() * 2);
          for (let inputIndex = 0; inputIndex < numInputs; inputIndex++) {
            const inputTemplate = inputTemplates[inputIndex % inputTemplates.length];
            const inputId = new ObjectId();
            
            const appliedAt = new Date();
            appliedAt.setDate(appliedAt.getDate() - Math.floor(Math.random() * 30));
            
            const inputTimestamp = Date.now() + inputIndex;
            const inputDateObj = { $date: { $numberLong: String(inputTimestamp) } };

            await prisma.$runCommandRaw({
              insert: "InputLog",
              documents: [{
                _id: { $oid: inputId.toHexString() },
                type: inputTemplate.type,
                name: inputTemplate.name,
                nameAr: inputTemplate.nameAr,
                brand: inputTemplate.brand,
                quantity: inputTemplate.quantity,
                unit: inputTemplate.unit,
                cost: inputTemplate.cost,
                currency: "DZD",
                appliedAt: { $date: { $numberLong: String(appliedAt.getTime()) } },
                cropCycleId: { $oid: cropCycleId.toHexString() },
                createdAt: inputDateObj,
              }]
            });

            totalInputs++;
          }
        }
      }

      // Create 2-4 equipment per farm
      const numEquipment = 2 + (farmIndex % 3);
      for (let eqIndex = 0; eqIndex < numEquipment; eqIndex++) {
        const eqTemplate = equipmentTemplates[eqIndex % equipmentTemplates.length];
        const equipmentId = new ObjectId();

        await prisma.$runCommandRaw({
          insert: "Equipment",
          documents: [{
            _id: { $oid: equipmentId.toHexString() },
            name: eqTemplate.name,
            type: eqTemplate.type,
            condition: eqTemplate.condition,
            quantity: eqTemplate.quantity,
            farmId: { $oid: farmId.toHexString() },
          }]
        });

        totalEquipment++;
      }
    }

    // Seed reference crops if not exists
    const existingCrops = await prisma.$runCommandRaw({
      find: "Crop",
      filter: {},
      limit: 1
    }) as { cursor?: { firstBatch?: unknown[] } };

    if (!existingCrops.cursor?.firstBatch?.length) {
      const refCrops = [
        { code: "wheat", nameAr: "القمح الصلب", nameFr: "Blé Dur", nameEn: "Durum Wheat", icon: "🌾", category: "cereals" },
        { code: "barley", nameAr: "الشعير", nameFr: "Orge", nameEn: "Barley", icon: "🌾", category: "cereals" },
        { code: "potato", nameAr: "البطاطا", nameFr: "Pomme de Terre", nameEn: "Potato", icon: "🥔", category: "vegetables" },
        { code: "tomato", nameAr: "الطماطم", nameFr: "Tomate", nameEn: "Tomato", icon: "🍅", category: "vegetables" },
        { code: "onion", nameAr: "البصل", nameFr: "Oignon", nameEn: "Onion", icon: "🧅", category: "vegetables" },
        { code: "olive", nameAr: "الزيتون", nameFr: "Olive", nameEn: "Olive", icon: "🫒", category: "tree_crops" },
        { code: "date_palm", nameAr: "نخيل التمر", nameFr: "Palmier Dattier", nameEn: "Date Palm", icon: "🌴", category: "tree_crops" },
      ];

      for (const crop of refCrops) {
        const cropId = new ObjectId();
        await prisma.$runCommandRaw({
          insert: "Crop",
          documents: [{
            _id: { $oid: cropId.toHexString() },
            ...crop,
            minTemp: 5,
            maxTemp: 40,
            soilPreferences: ["LOAM", "CLAY"],
            commonPests: [],
            commonDiseases: [],
            createdAt: dateObj,
            updatedAt: dateObj,
          }]
        });
      }
    }

    return NextResponse.json({
      success: true,
      message: "تم إنشاء البيانات التجريبية الكاملة",
      stats: {
        farms: farms.length,
        plots: totalPlots,
        cropCycles: totalCrops,
        tasks: totalTasks,
        equipment: totalEquipment,
        inputs: totalInputs,
      }
    });

  } catch (error) {
    console.error("Error seeding complete data:", error);
    return NextResponse.json(
      { success: false, error: String(error) },
      { status: 500 }
    );
  }
}

export async function DELETE() {
  try {
    // Clear all seeded data except farms and users
    const collections = ["Plot", "CropCycle", "CropTask", "InputLog", "Equipment", "CropObservation"];
    
    for (const collection of collections) {
      await prisma.$runCommandRaw({
        delete: collection,
        deletes: [{ q: {}, limit: 0 }]
      });
    }

    return NextResponse.json({
      success: true,
      message: "تم حذف البيانات التفصيلية (القطع، المحاصيل، المهام، المعدات)"
    });

  } catch (error) {
    console.error("Error clearing detailed data:", error);
    return NextResponse.json(
      { success: false, error: String(error) },
      { status: 500 }
    );
  }
}

export async function GET() {
  return NextResponse.json({
    info: "Complete Demo Data Seeder API",
    endpoints: {
      "POST /api/seed/complete": "إنشاء قطع ومحاصيل ومهام ومعدات للمزارع الموجودة",
      "DELETE /api/seed/complete": "حذف البيانات التفصيلية فقط"
    }
  });
}
