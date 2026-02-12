// AgriBrain - Advanced Scenario Simulator
// What-if analysis for agricultural decision making

interface ScenarioInput {
  cropCode: string;
  plotArea: number;
  wilayaCode: string;
  currentWeather: {
    temperature: number;
    humidity: number;
    rainfall: number;
  };
  scenarios: ScenarioType[];
}

type ScenarioType = 
  | "drought"
  | "heavy_rain"
  | "frost"
  | "heatwave"
  | "pest_outbreak"
  | "market_crash"
  | "market_boom"
  | "delayed_planting"
  | "early_harvest"
  | "no_fertilizer"
  | "organic_only"
  | "double_irrigation";

interface ScenarioResult {
  scenario: ScenarioType;
  nameAr: string;
  description: string;
  descriptionAr: string;
  yieldImpact: number; // percentage change
  revenueImpact: number;
  riskLevel: "low" | "medium" | "high" | "critical";
  mitigations: string[];
  mitigationsAr: string[];
  probabilityThisSeason: number; // 0-100
}

const scenarioDefinitions: Record<ScenarioType, {
  nameAr: string;
  descriptionAr: string;
  yieldImpact: number;
  revenueMultiplier: number;
  risk: ScenarioResult["riskLevel"];
}> = {
  drought: {
    nameAr: "جفاف شديد",
    descriptionAr: "انخفاض هطول الأمطار بنسبة 50% عن المعتاد",
    yieldImpact: -40,
    revenueMultiplier: 1.2, // prices rise
    risk: "critical",
  },
  heavy_rain: {
    nameAr: "أمطار غزيرة",
    descriptionAr: "هطول أمطار ضعف المعدل الموسمي",
    yieldImpact: -25,
    revenueMultiplier: 0.9,
    risk: "high",
  },
  frost: {
    nameAr: "موجة صقيع",
    descriptionAr: "انخفاض درجات الحرارة تحت الصفر لعدة أيام",
    yieldImpact: -60,
    revenueMultiplier: 1.4,
    risk: "critical",
  },
  heatwave: {
    nameAr: "موجة حر",
    descriptionAr: "درجات حرارة تتجاوز 45 درجة لأسبوع أو أكثر",
    yieldImpact: -35,
    revenueMultiplier: 1.1,
    risk: "high",
  },
  pest_outbreak: {
    nameAr: "انتشار آفات",
    descriptionAr: "هجوم كبير للآفات على المحاصيل",
    yieldImpact: -45,
    revenueMultiplier: 1.3,
    risk: "critical",
  },
  market_crash: {
    nameAr: "انهيار الأسعار",
    descriptionAr: "انخفاض أسعار السوق بنسبة 40%",
    yieldImpact: 0,
    revenueMultiplier: 0.6,
    risk: "high",
  },
  market_boom: {
    nameAr: "ارتفاع الأسعار",
    descriptionAr: "ارتفاع أسعار السوق بنسبة 50%",
    yieldImpact: 0,
    revenueMultiplier: 1.5,
    risk: "low",
  },
  delayed_planting: {
    nameAr: "تأخر الزراعة",
    descriptionAr: "تأخر موعد الزراعة بشهر عن الموعد المثالي",
    yieldImpact: -20,
    revenueMultiplier: 0.95,
    risk: "medium",
  },
  early_harvest: {
    nameAr: "حصاد مبكر",
    descriptionAr: "حصاد المحصول قبل النضج الكامل",
    yieldImpact: -15,
    revenueMultiplier: 1.1,
    risk: "medium",
  },
  no_fertilizer: {
    nameAr: "بدون تسميد",
    descriptionAr: "عدم استخدام أي أسمدة كيميائية",
    yieldImpact: -30,
    revenueMultiplier: 1.2, // organic premium
    risk: "medium",
  },
  organic_only: {
    nameAr: "زراعة عضوية",
    descriptionAr: "استخدام المدخلات العضوية فقط",
    yieldImpact: -25,
    revenueMultiplier: 1.4,
    risk: "low",
  },
  double_irrigation: {
    nameAr: "ري مضاعف",
    descriptionAr: "مضاعفة كمية مياه الري",
    yieldImpact: 15,
    revenueMultiplier: 0.95, // higher costs
    risk: "low",
  },
};

const mitigations: Record<ScenarioType, { en: string[]; ar: string[] }> = {
  drought: {
    en: ["Install drip irrigation", "Use mulching", "Choose drought-resistant varieties", "Build water storage"],
    ar: ["تركيب ري بالتنقيط", "استخدام التغطية", "اختيار أصناف مقاومة للجفاف", "بناء خزانات مياه"],
  },
  heavy_rain: {
    en: ["Improve drainage", "Use raised beds", "Apply fungicides preventively"],
    ar: ["تحسين الصرف", "استخدام الأحواض المرتفعة", "رش مبيدات فطرية وقائية"],
  },
  frost: {
    en: ["Cover crops with frost cloth", "Use smudge pots", "Plant in protected areas"],
    ar: ["تغطية المحاصيل بقماش الصقيع", "استخدام مواقد التدفئة", "الزراعة في مناطق محمية"],
  },
  heatwave: {
    en: ["Increase irrigation frequency", "Use shade cloth", "Mulch heavily", "Harvest early if needed"],
    ar: ["زيادة تكرار الري", "استخدام شبكات التظليل", "تغطية مكثفة", "الحصاد المبكر عند الضرورة"],
  },
  pest_outbreak: {
    en: ["Apply integrated pest management", "Use biological control", "Monitor regularly", "Quarantine affected areas"],
    ar: ["تطبيق المكافحة المتكاملة", "استخدام المكافحة الحيوية", "المراقبة المنتظمة", "عزل المناطق المصابة"],
  },
  market_crash: {
    en: ["Diversify crops", "Build storage capacity", "Contract selling in advance", "Process into value-added products"],
    ar: ["تنويع المحاصيل", "بناء سعة تخزين", "البيع بعقود مسبقة", "التصنيع للقيمة المضافة"],
  },
  market_boom: {
    en: ["Maximize harvest", "Sell quickly at peak prices", "Negotiate bulk contracts"],
    ar: ["تعظيم الحصاد", "البيع بسرعة عند ذروة الأسعار", "التفاوض على عقود بالجملة"],
  },
  delayed_planting: {
    en: ["Use fast-maturing varieties", "Start seedlings indoors", "Prepare soil in advance"],
    ar: ["استخدام أصناف سريعة النضج", "بدء الشتلات داخلياً", "تحضير التربة مسبقاً"],
  },
  early_harvest: {
    en: ["Store properly to allow ripening", "Target early-season premium markets"],
    ar: ["التخزين السليم للسماح بالنضج", "استهداف أسواق البواكير"],
  },
  no_fertilizer: {
    en: ["Use compost and manure", "Plant nitrogen-fixing cover crops", "Rotate with legumes"],
    ar: ["استخدام السماد العضوي", "زراعة محاصيل تثبت النيتروجين", "تناوب مع البقوليات"],
  },
  organic_only: {
    en: ["Get organic certification", "Build soil health long-term", "Target premium markets"],
    ar: ["الحصول على شهادة عضوية", "بناء صحة التربة على المدى الطويل", "استهداف الأسواق المتميزة"],
  },
  double_irrigation: {
    en: ["Monitor for waterlogging", "Adjust based on soil type", "Track water costs"],
    ar: ["مراقبة التشبع المائي", "التعديل حسب نوع التربة", "تتبع تكاليف المياه"],
  },
};

// Seasonal probability based on Algerian climate patterns
function getSeasonalProbability(scenario: ScenarioType, wilayaCode: string, month: number): number {
  const isNorth = parseInt(wilayaCode) <= 25;
  const isSaharan = ["30", "39", "47", "33", "07", "03", "11"].includes(wilayaCode);
  const isWinter = month >= 11 || month <= 2;
  const isSummer = month >= 6 && month <= 8;
  
  switch (scenario) {
    case "drought":
      return isSaharan ? 60 : (isSummer ? 40 : 15);
    case "heavy_rain":
      return isNorth && isWinter ? 35 : 10;
    case "frost":
      return isWinter && !isSaharan ? 25 : 5;
    case "heatwave":
      return isSummer ? (isSaharan ? 70 : 45) : 10;
    case "pest_outbreak":
      return isSummer ? 30 : 15;
    case "market_crash":
      return 15; // Economic uncertainty
    case "market_boom":
      return 20;
    default:
      return 10;
  }
}

export function simulateScenarios(input: ScenarioInput): ScenarioResult[] {
  const month = new Date().getMonth();
  
  return input.scenarios.map(scenario => {
    const def = scenarioDefinitions[scenario];
    const mit = mitigations[scenario];
    const probability = getSeasonalProbability(scenario, input.wilayaCode, month);
    
    return {
      scenario,
      nameAr: def.nameAr,
      description: `What if: ${scenario.replace(/_/g, " ")}`,
      descriptionAr: def.descriptionAr,
      yieldImpact: def.yieldImpact,
      revenueImpact: Math.round((def.revenueMultiplier - 1) * 100),
      riskLevel: def.risk,
      mitigations: mit.en,
      mitigationsAr: mit.ar,
      probabilityThisSeason: probability,
    };
  });
}

export function getAllScenarios(): { code: ScenarioType; nameAr: string; category: string }[] {
  return [
    { code: "drought", nameAr: "جفاف", category: "weather" },
    { code: "heavy_rain", nameAr: "أمطار غزيرة", category: "weather" },
    { code: "frost", nameAr: "صقيع", category: "weather" },
    { code: "heatwave", nameAr: "موجة حر", category: "weather" },
    { code: "pest_outbreak", nameAr: "آفات", category: "biological" },
    { code: "market_crash", nameAr: "انهيار أسعار", category: "market" },
    { code: "market_boom", nameAr: "ارتفاع أسعار", category: "market" },
    { code: "delayed_planting", nameAr: "تأخر زراعة", category: "management" },
    { code: "early_harvest", nameAr: "حصاد مبكر", category: "management" },
    { code: "no_fertilizer", nameAr: "بدون تسميد", category: "input" },
    { code: "organic_only", nameAr: "عضوي", category: "input" },
    { code: "double_irrigation", nameAr: "ري مضاعف", category: "input" },
  ];
}
