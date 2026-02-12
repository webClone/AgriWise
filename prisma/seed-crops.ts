
import { PrismaClient } from "@prisma/client";

const prisma = new PrismaClient();

async function main() {
  console.log("Seeding crop reference data...");

  // 1. Wheat (Cereal)
  await prisma.crop.upsert({
    where: { code: "wheat" },
    update: {},
    create: {
      code: "wheat",
      nameAr: "القمح الصلب",
      nameFr: "Blé Dur",
      nameEn: "Durum Wheat",
      icon: "🌾",
      category: "cereals",
      stages: [
        { stage: "sowing", nameAr: "البذر", tasks: ["حراثة التربة", "البذر", "التسميد الأساسي"] },
        { stage: "emergence", nameAr: "الإنبات", tasks: ["مراقبة الإنبات", "الري التكميلي"] },
        { stage: "tillering", nameAr: "التفريع", tasks: ["التسميد الآزوتي", "مكافحة الأعشاب الضارة"] },
        { stage: "heading", nameAr: "الإسبال", tasks: ["الري التكميلي", "مراقبة الأمراض الفطرية"] },
        { stage: "ripening", nameAr: "النضج", tasks: ["وقف الري", "الاستعداد للحصاد"] },
      ],
      waterRequirements: { early: "low", mid: "medium", late: "low" },
      nutrientNeeds: { N: "high", P: "medium", K: "low" },
      soilPreferences: ["CLAY", "LOAM"],
      minTemp: 5,
      maxTemp: 35,
      seasonality: {
        north: { plant: [10, 11, 12], harvest: [5, 6] }, // Oct-Dec -> May-Jun
        south: { plant: [11, 12], harvest: [4, 5] },
      },
      recommendations: {
        general: "Best planted after first autumn rains. Needs nitrogen split application.",
      },
      commonPests: ["من", "خنافس"],
      commonDiseases: ["صدأ", "تبقع"],
    },
  });

  // 2. Potato (Vegetable)
  await prisma.crop.upsert({
    where: { code: "potato" },
    update: {},
    create: {
      code: "potato",
      nameAr: "البطاطا",
      nameFr: "Pomme de Terre",
      nameEn: "Potato",
      icon: "🥔",
      category: "vegetables",
      stages: [
        { stage: "planting", nameAr: "الغرس", tasks: ["تحضير الدرنات", "الغرس", "التسميد"] },
        { stage: "vegetative", nameAr: "النمو الخضري", tasks: ["الري المنتظم", "التحضين", "التسميد الآزوتي"] },
        { stage: "tuberization", nameAr: "تكوين الدرنات", tasks: ["زيادة الري", "تسميد بوتاسي", "مكافحة الميلديو"] },
        { stage: "maturation", nameAr: "النضج", tasks: ["تخفيف الري", "مراقبة القرعيات"] },
      ],
      waterRequirements: { early: "medium", mid: "high", late: "low" },
      nutrientNeeds: { N: "high", P: "high", K: "very_high" },
      soilPreferences: ["SANDY", "LOAM"],
      minTemp: 10,
      maxTemp: 30,
      seasonality: {
        coastal: { plant: [1, 2, 8, 9], harvest: [5, 6, 11, 12] }, // Seasonal & Arrière-saison
        interior: { plant: [2, 3], harvest: [6, 7] },
      },
      recommendations: {
        general: "Requires loose soil. Watch out for Late Blight (Mildiou).",
      },
      commonPests: ["فراشة البطاطا", "نيماتودا"],
      commonDiseases: ["ميلديو", "جرب"],
    },
  });

  // 3. Tomato (Vegetable)
  await prisma.crop.upsert({
    where: { code: "tomato" },
    update: {},
    create: {
      code: "tomato",
      nameAr: "الطماطم",
      nameFr: "Tomate",
      nameEn: "Tomato",
      icon: "🍅",
      category: "vegetables",
      stages: [
        { stage: "planting", nameAr: "الشتل", tasks: ["إعداد الشتلات", "الشتل", "الري"] },
        { stage: "flowering", nameAr: "الإزهار", tasks: ["التهوية", "تسميد متوازن", "تعليق النباتات"] },
        { stage: "fruiting", nameAr: "الإثمار", tasks: ["تسميد بوتاسي", "ري منتظم", "جني تدريجي"] },
      ],
      waterRequirements: { early: "medium", mid: "high", late: "medium" },
      nutrientNeeds: { N: "medium", P: "high", K: "high" },
      soilPreferences: ["LOAM", "SANDY"],
      minTemp: 15,
      maxTemp: 35,
      seasonality: {
        open_field: { plant: [3, 4], harvest: [6, 7, 8] },
        greenhouse: { plant: [9, 10], harvest: [1, 2, 3, 4, 5] },
      },
      recommendations: {
        general: "Drip irrigation is highly recommended to prevent fungal diseases.",
      },
      commonPests: ["توتا أبسولوتا", "ذبابة بيضاء"],
      commonDiseases: ["بياض دقيقي", "تعفن"],
    },
  });

  // 4. Date Palm (Tree)
  await prisma.crop.upsert({
    where: { code: "date_palm" },
    update: {},
    create: {
      code: "date_palm",
      nameAr: "نخيل التمر",
      nameFr: "Palmier Dattier",
      nameEn: "Date Palm",
      icon: "🌴",
      category: "tree_crops",
      stages: [
        { stage: "pollination", nameAr: "التلقيح", tasks: ["التلقيح اليدوي", "تنظيف الجريد"] },
        { stage: "thinning", nameAr: "الخف", tasks: ["خف الثمار", "تعديل العراجين"] },
        { stage: "maturation", nameAr: "النضج (البسر/الرطب)", tasks: ["تغطي العراجين", "الري الغزير"] },
        { stage: "harvest", nameAr: "جني التمور", tasks: ["قطع العراجين", "الفرز", "التخزين"] },
      ],
      waterRequirements: { early: "medium", mid: "high", late: "low" },
      nutrientNeeds: { N: "medium", P: "low", K: "medium" },
      soilPreferences: ["SANDY", "LOAM"],
      minTemp: -5,
      maxTemp: 50,
      seasonality: {
        sahara: { plant: [1, 12], harvest: [9, 10, 11] }, // Harvest in autumn
      },
      recommendations: {
        general: "Requires pollination in March/April. Critical for desert economy.",
      },
      commonPests: ["سوسة النخيل", "بوفروة"],
      commonDiseases: ["بيوض"],
    },
  });

  console.log("Seeding completed.");
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
