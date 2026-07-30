// AgriBrain - Comprehensive Crop Analysis
// Detailed AI-powered crop recommendations and analysis

interface CropAnalysisInput {
  cropCode: string;
  wilayaCode: string;
  plotArea: number;
  soilType: string;
  irrigationType: string;
  plantDate: Date;
  budget?: number; // DZD
  laborAvailable?: number; // person-days per week
  equipment?: string[];
  previousCrop?: string;
  goals?: ("maximize_yield" | "minimize_cost" | "organic" | "quick_harvest" | "storage")[];
}

interface DetailedAnalysis {
  // Basic Info
  cropInfo: {
    nameAr: string;
    scientificName: string;
    family: string;
    growingDays: number;
    optimalTemp: { min: number; max: number };
    waterNeeds: "low" | "medium" | "high";
  };
  
  // Suitability Score
  suitability: {
    overall: number; // 0-100
    climate: number;
    soil: number;
    water: number;
    market: number;
    reasons: string[];
    reasonsAr: string[];
  };
  
  // Growth Timeline
  timeline: {
    phase: string;
    phaseAr: string;
    startDay: number;
    endDay: number;
    tasks: { nameAr: string; critical: boolean }[];
  }[];
  
  // Input Requirements
  inputs: {
    category: string;
    categoryAr: string;
    items: {
      name: string;
      nameAr: string;
      quantity: string;
      timing: string;
      timingAr: string;
      estimatedCost: number;
      priority: "essential" | "recommended" | "optional";
    }[];
  }[];
  
  // Risk Analysis
  risks: {
    type: string;
    typeAr: string;
    probability: "low" | "medium" | "high";
    impact: "low" | "medium" | "high";
    descriptionAr: string;
    preventionAr: string;
  }[];
  
  // Financial Projection
  financials: {
    estimatedCosts: {
      seeds: number;
      fertilizers: number;
      pesticides: number;
      irrigation: number;
      labor: number;
      equipment: number;
      total: number;
    };
    estimatedRevenue: {
      minPrice: number;
      maxPrice: number;
      expectedYield: number;
      minRevenue: number;
      maxRevenue: number;
    };
    profitMargin: number;
    breakEvenYield: number;
    roi: number;
  };
  
  // Optimization Tips
  optimizations: {
    titleAr: string;
    descriptionAr: string;
    impact: string;
    difficulty: "easy" | "medium" | "hard";
    investmentNeeded: number;
  }[];
}

const cropDatabase: Record<string, {
  nameAr: string;
  scientificName: string;
  family: string;
  growingDays: number;
  optimalTemp: { min: number; max: number };
  waterNeeds: "low" | "medium" | "high";
  soilPreference: string[];
  priceRange: { min: number; max: number }; // DZD per quintal
}> = {
  wheat: {
    nameAr: "قمح",
    scientificName: "Triticum aestivum",
    family: "Poaceae",
    growingDays: 150,
    optimalTemp: { min: 15, max: 25 },
    waterNeeds: "medium",
    soilPreference: ["loamy", "clay"],
    priceRange: { min: 5000, max: 7000 },
  },
  barley: {
    nameAr: "شعير",
    scientificName: "Hordeum vulgare",
    family: "Poaceae",
    growingDays: 130,
    optimalTemp: { min: 12, max: 22 },
    waterNeeds: "low",
    soilPreference: ["loamy", "sandy"],
    priceRange: { min: 4500, max: 6000 },
  },
  potato: {
    nameAr: "بطاطا",
    scientificName: "Solanum tuberosum",
    family: "Solanaceae",
    growingDays: 110,
    optimalTemp: { min: 15, max: 22 },
    waterNeeds: "high",
    soilPreference: ["loamy", "sandy"],
    priceRange: { min: 3000, max: 6000 },
  },
  tomato: {
    nameAr: "طماطم",
    scientificName: "Solanum lycopersicum",
    family: "Solanaceae",
    growingDays: 80,
    optimalTemp: { min: 20, max: 30 },
    waterNeeds: "high",
    soilPreference: ["loamy"],
    priceRange: { min: 2000, max: 5000 },
  },
  olive: {
    nameAr: "زيتون",
    scientificName: "Olea europaea",
    family: "Oleaceae",
    growingDays: 200,
    optimalTemp: { min: 15, max: 35 },
    waterNeeds: "low",
    soilPreference: ["loamy", "clay", "rocky"],
    priceRange: { min: 15000, max: 25000 },
  },
  date: {
    nameAr: "تمر",
    scientificName: "Phoenix dactylifera",
    family: "Arecaceae",
    growingDays: 180,
    optimalTemp: { min: 25, max: 45 },
    waterNeeds: "medium",
    soilPreference: ["sandy", "loamy"],
    priceRange: { min: 20000, max: 50000 },
  },
  onion: {
    nameAr: "بصل",
    scientificName: "Allium cepa",
    family: "Amaryllidaceae",
    growingDays: 120,
    optimalTemp: { min: 12, max: 25 },
    waterNeeds: "medium",
    soilPreference: ["loamy"],
    priceRange: { min: 3000, max: 5000 },
  },
};

function generateTimeline(cropCode: string, plantDate: Date): DetailedAnalysis["timeline"] {
  const crop = cropDatabase[cropCode];
  if (!crop) return [];
  
  const totalDays = crop.growingDays;
  
  return [
    {
      phase: "Preparation",
      phaseAr: "التحضير",
      startDay: -14,
      endDay: 0,
      tasks: [
        { nameAr: "تحضير التربة وحرثها", critical: true },
        { nameAr: "تحليل التربة", critical: false },
        { nameAr: "إضافة السماد الأساسي", critical: true },
      ],
    },
    {
      phase: "Planting",
      phaseAr: "الزراعة",
      startDay: 0,
      endDay: 7,
      tasks: [
        { nameAr: "الزراعة", critical: true },
        { nameAr: "الري الأولي", critical: true },
      ],
    },
    {
      phase: "Establishment",
      phaseAr: "التأسيس",
      startDay: 7,
      endDay: Math.round(totalDays * 0.2),
      tasks: [
        { nameAr: "مراقبة الإنبات", critical: true },
        { nameAr: "إزالة الأعشاب الضارة", critical: true },
        { nameAr: "الري المنتظم", critical: true },
      ],
    },
    {
      phase: "Vegetative Growth",
      phaseAr: "النمو الخضري",
      startDay: Math.round(totalDays * 0.2),
      endDay: Math.round(totalDays * 0.5),
      tasks: [
        { nameAr: "التسميد الأول", critical: true },
        { nameAr: "مكافحة الآفات", critical: true },
        { nameAr: "تعديل الري حسب الحاجة", critical: false },
      ],
    },
    {
      phase: "Flowering/Fruiting",
      phaseAr: "الإزهار والإثمار",
      startDay: Math.round(totalDays * 0.5),
      endDay: Math.round(totalDays * 0.75),
      tasks: [
        { nameAr: "التسميد الثاني", critical: true },
        { nameAr: "زيادة الري", critical: true },
        { nameAr: "مراقبة الأمراض", critical: true },
      ],
    },
    {
      phase: "Maturation",
      phaseAr: "النضج",
      startDay: Math.round(totalDays * 0.75),
      endDay: totalDays,
      tasks: [
        { nameAr: "تقليل الري تدريجياً", critical: false },
        { nameAr: "مراقبة علامات النضج", critical: true },
        { nameAr: "التحضير للحصاد", critical: true },
      ],
    },
    {
      phase: "Harvest",
      phaseAr: "الحصاد",
      startDay: totalDays,
      endDay: totalDays + 14,
      tasks: [
        { nameAr: "الحصاد في الوقت المناسب", critical: true },
        { nameAr: "الفرز والتصنيف", critical: false },
        { nameAr: "التخزين أو البيع", critical: true },
      ],
    },
  ];
}

function calculateInputs(cropCode: string, plotArea: number): DetailedAnalysis["inputs"] {
  const costPerHa: Record<string, { seeds: number; fert: number; pest: number }> = {
    wheat: { seeds: 15000, fert: 25000, pest: 10000 },
    barley: { seeds: 12000, fert: 20000, pest: 8000 },
    potato: { seeds: 80000, fert: 40000, pest: 20000 },
    tomato: { seeds: 30000, fert: 50000, pest: 30000 },
    olive: { seeds: 5000, fert: 30000, pest: 15000 },
    date: { seeds: 10000, fert: 25000, pest: 10000 },
    onion: { seeds: 25000, fert: 30000, pest: 15000 },
  };
  
  const costs = costPerHa[cropCode] || costPerHa.wheat;
  
  return [
    {
      category: "Seeds/Seedlings",
      categoryAr: "البذور والشتلات",
      items: [
        {
          name: "Quality seeds",
          nameAr: "بذور معتمدة",
          quantity: `${Math.round(plotArea * 120)} كغ`,
          timing: "At planting",
          timingAr: "عند الزراعة",
          estimatedCost: costs.seeds * plotArea,
          priority: "essential",
        },
      ],
    },
    {
      category: "Fertilizers",
      categoryAr: "الأسمدة",
      items: [
        {
          name: "Base fertilizer (NPK)",
          nameAr: "سماد أساسي (NPK)",
          quantity: `${Math.round(plotArea * 200)} كغ`,
          timing: "Before planting",
          timingAr: "قبل الزراعة",
          estimatedCost: costs.fert * plotArea * 0.4,
          priority: "essential",
        },
        {
          name: "Nitrogen (Urea)",
          nameAr: "أزوت (يوريا)",
          quantity: `${Math.round(plotArea * 150)} كغ`,
          timing: "30 days after planting",
          timingAr: "30 يوم بعد الزراعة",
          estimatedCost: costs.fert * plotArea * 0.3,
          priority: "essential",
        },
        {
          name: "Foliar fertilizer",
          nameAr: "سماد ورقي",
          quantity: `${Math.round(plotArea * 5)} لتر`,
          timing: "Flowering stage",
          timingAr: "مرحلة الإزهار",
          estimatedCost: costs.fert * plotArea * 0.3,
          priority: "recommended",
        },
      ],
    },
    {
      category: "Crop Protection",
      categoryAr: "وقاية النبات",
      items: [
        {
          name: "Fungicide",
          nameAr: "مبيد فطري",
          quantity: `${Math.round(plotArea * 3)} لتر`,
          timing: "Preventive application",
          timingAr: "رش وقائي",
          estimatedCost: costs.pest * plotArea * 0.4,
          priority: "recommended",
        },
        {
          name: "Insecticide",
          nameAr: "مبيد حشري",
          quantity: `${Math.round(plotArea * 2)} لتر`,
          timing: "As needed",
          timingAr: "عند الحاجة",
          estimatedCost: costs.pest * plotArea * 0.4,
          priority: "essential",
        },
        {
          name: "Herbicide",
          nameAr: "مبيد أعشاب",
          quantity: `${Math.round(plotArea * 4)} لتر`,
          timing: "Early growth",
          timingAr: "بداية النمو",
          estimatedCost: costs.pest * plotArea * 0.2,
          priority: "optional",
        },
      ],
    },
  ];
}

function analyzeRisks(cropCode: string, wilayaCode: string): DetailedAnalysis["risks"] {
  const isSaharan = ["30", "39", "47", "33", "07"].includes(wilayaCode);
  const isCoastal = ["16", "09", "42", "23", "06"].includes(wilayaCode);
  
  const risks: DetailedAnalysis["risks"] = [
    {
      type: "Drought",
      typeAr: "الجفاف",
      probability: isSaharan ? "high" : "medium",
      impact: "high",
      descriptionAr: "نقص المياه يؤثر مباشرة على الإنتاج",
      preventionAr: "تركيب ري بالتنقيط وبناء خزانات",
    },
    {
      type: "Pests",
      typeAr: "الآفات",
      probability: "medium",
      impact: "high",
      descriptionAr: "الحشرات والأمراض تهدد المحصول",
      preventionAr: "المراقبة المستمرة واستخدام المكافحة المتكاملة",
    },
    {
      type: "Price Volatility",
      typeAr: "تقلب الأسعار",
      probability: "medium",
      impact: "medium",
      descriptionAr: "تغيرات الأسعار تؤثر على الربحية",
      preventionAr: "التعاقد المسبق وتنويع قنوات البيع",
    },
  ];
  
  if (isCoastal) {
    risks.push({
      type: "Excessive Rain",
      typeAr: "الأمطار الغزيرة",
      probability: "medium",
      impact: "medium",
      descriptionAr: "الأمطار الزائدة تسبب أمراضاً فطرية",
      preventionAr: "تحسين الصرف ورش مبيدات فطرية وقائية",
    });
  }
  
  if (isSaharan && cropCode !== "date") {
    risks.push({
      type: "Heat Stress",
      typeAr: "الإجهاد الحراري",
      probability: "high",
      impact: "high",
      descriptionAr: "درجات الحرارة العالية تضر بالمحصول",
      preventionAr: "استخدام شبكات التظليل وزيادة الري",
    });
  }
  
  return risks;
}

export function generateDetailedAnalysis(input: CropAnalysisInput): DetailedAnalysis {
  const crop = cropDatabase[input.cropCode] || cropDatabase.wheat;
  const plantDate = new Date(input.plantDate);
  
  // Calculate suitability
  const soilMatch = crop.soilPreference.includes(input.soilType) ? 90 : 60;
  const waterMatch = input.irrigationType === "rainfed" ? (crop.waterNeeds === "low" ? 80 : 50) : 85;
  const climateFit = 75; // Simplified
  const marketScore = 80;
  const overall = Math.round((soilMatch + waterMatch + climateFit + marketScore) / 4);
  
  // Calculate financials
  const inputs = calculateInputs(input.cropCode, input.plotArea);
  const seedCost = inputs[0].items.reduce((sum, i) => sum + i.estimatedCost, 0);
  const fertCost = inputs[1].items.reduce((sum, i) => sum + i.estimatedCost, 0);
  const pestCost = inputs[2].items.reduce((sum, i) => sum + i.estimatedCost, 0);
  const irrigationCost = input.irrigationType === "rainfed" ? 0 : 30000 * input.plotArea;
  const laborCost = 50000 * input.plotArea;
  const equipmentCost = 20000 * input.plotArea;
  const totalCost = seedCost + fertCost + pestCost + irrigationCost + laborCost + equipmentCost;
  
  const baseYield = crop.growingDays < 100 ? 300 : (crop.growingDays < 150 ? 25 : 35);
  const expectedYield = baseYield * input.plotArea;
  const minRevenue = expectedYield * crop.priceRange.min;
  const maxRevenue = expectedYield * crop.priceRange.max;
  const avgRevenue = (minRevenue + maxRevenue) / 2;
  const profitMargin = Math.round(((avgRevenue - totalCost) / avgRevenue) * 100);
  const roi = Math.round(((avgRevenue - totalCost) / totalCost) * 100);
  const breakEvenYield = Math.round(totalCost / ((crop.priceRange.min + crop.priceRange.max) / 2));
  
  return {
    cropInfo: {
      nameAr: crop.nameAr,
      scientificName: crop.scientificName,
      family: crop.family,
      growingDays: crop.growingDays,
      optimalTemp: crop.optimalTemp,
      waterNeeds: crop.waterNeeds,
    },
    suitability: {
      overall,
      climate: climateFit,
      soil: soilMatch,
      water: waterMatch,
      market: marketScore,
      reasons: overall >= 75 ? ["Good match for your conditions"] : ["Some challenges to consider"],
      reasonsAr: overall >= 75 ? ["ملائم لظروفك"] : ["بعض التحديات للنظر فيها"],
    },
    timeline: generateTimeline(input.cropCode, plantDate),
    inputs,
    risks: analyzeRisks(input.cropCode, input.wilayaCode),
    financials: {
      estimatedCosts: {
        seeds: seedCost,
        fertilizers: fertCost,
        pesticides: pestCost,
        irrigation: irrigationCost,
        labor: laborCost,
        equipment: equipmentCost,
        total: totalCost,
      },
      estimatedRevenue: {
        minPrice: crop.priceRange.min,
        maxPrice: crop.priceRange.max,
        expectedYield,
        minRevenue,
        maxRevenue,
      },
      profitMargin,
      breakEvenYield,
      roi,
    },
    optimizations: [
      {
        titleAr: "تحسين الري",
        descriptionAr: "الترقية إلى الري بالتنقيط يوفر 30% من المياه ويزيد الإنتاج 20%",
        impact: "+20% إنتاج",
        difficulty: "medium",
        investmentNeeded: 100000 * input.plotArea,
      },
      {
        titleAr: "تحليل التربة",
        descriptionAr: "تحليل التربة يحسن كفاءة التسميد ويوفر 15% من التكاليف",
        impact: "-15% تكاليف",
        difficulty: "easy",
        investmentNeeded: 5000,
      },
      {
        titleAr: "التسويق المباشر",
        descriptionAr: "البيع المباشر للمستهلك يزيد هامش الربح 25%",
        impact: "+25% ربح",
        difficulty: "hard",
        investmentNeeded: 50000,
      },
    ],
  };
}
