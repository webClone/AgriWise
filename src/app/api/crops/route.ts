
import { NextResponse } from "next/server";

// Full 209-crop registry — matches the backend `crop_database.registry`.
// Organized by architecture class.

const CROP_EMOJI: Record<string, string> = {
  cereal: "🌾",
  maize: "🌽",
  rice: "🌾",
  legume: "🫘",
  root_tuber: "🥔",
  vegetable: "🥬",
  cucurbit: "🍉",
  allium: "🧅",
  brassica: "🥦",
  leafy: "🥬",
  solanaceae: "🍅",
  perennial: "🌳",
  tropical_tree: "🌴",
  tropical_fruit: "🍌",
  berry: "🫐",
  nut: "🥜",
  fiber: "🧵",
  oilseed: "🌻",
  sugar: "🍬",
  stimulant: "☕",
  spice: "🌶️",
  forage: "🌿",
  industrial: "🏭",
  cover_crop: "🍀",
  vine: "🍇",
  cotton: "🧵",
};

// GET /api/crops - List available crops (209 types from full registry)
export async function GET() {
  try {
    // Try to fetch from the Python backend (canonical source)
    const apiUrl = process.env.AGRIBRAIN_API_URL || "http://127.0.0.1:8000";
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5_000);

    const response = await fetch(`${apiUrl}/v2/crops`, {
      signal: controller.signal,
    }).finally(() => clearTimeout(timeoutId));

    if (response.ok) {
      const data = await response.json();
      return NextResponse.json({ success: true, crops: data.crops, count: data.count, source: "registry" });
    }
  } catch {
    // Backend not available — fall back to static list
  }

  // Fallback: comprehensive static list (subset of the 209)
  const crops = [
    { code: "wheat", nameAr: "قمح (Wheat)", icon: "🌾", architecture: "cereal" },
    { code: "barley", nameAr: "شعير (Barley)", icon: "🌾", architecture: "cereal" },
    { code: "durum_wheat", nameAr: "قمح صلب (Durum Wheat)", icon: "🌾", architecture: "cereal" },
    { code: "oat", nameAr: "شوفان (Oat)", icon: "🌾", architecture: "cereal" },
    { code: "rye", nameAr: "شيلم (Rye)", icon: "🌾", architecture: "cereal" },
    { code: "triticale", nameAr: "تريتيكالي (Triticale)", icon: "🌾", architecture: "cereal" },
    { code: "sorghum", nameAr: "ذرة رفيعة (Sorghum)", icon: "🌾", architecture: "cereal" },
    { code: "millet", nameAr: "دخن (Millet)", icon: "🌾", architecture: "cereal" },
    { code: "maize", nameAr: "ذرة (Maize)", icon: "🌽", architecture: "maize" },
    { code: "rice", nameAr: "أرز (Rice)", icon: "🌾", architecture: "rice" },
    { code: "potato", nameAr: "بطاطا (Potato)", icon: "🥔", architecture: "root_tuber" },
    { code: "sweet_potato", nameAr: "بطاطا حلوة (Sweet Potato)", icon: "🍠", architecture: "root_tuber" },
    { code: "cassava", nameAr: "كسافا (Cassava)", icon: "🥔", architecture: "root_tuber" },
    { code: "yam", nameAr: "يام (Yam)", icon: "🥔", architecture: "root_tuber" },
    { code: "tomato", nameAr: "طماطم (Tomato)", icon: "🍅", architecture: "solanaceae" },
    { code: "pepper", nameAr: "فلفل (Pepper)", icon: "🌶️", architecture: "solanaceae" },
    { code: "eggplant", nameAr: "باذنجان (Eggplant)", icon: "🍆", architecture: "solanaceae" },
    { code: "olive", nameAr: "زيتون (Olive)", icon: "🫒", architecture: "perennial" },
    { code: "date_palm", nameAr: "نخيل التمر (Date Palm)", icon: "🌴", architecture: "tropical_tree" },
    { code: "grape", nameAr: "عنب (Grape)", icon: "🍇", architecture: "vine" },
    { code: "citrus", nameAr: "حمضيات (Citrus)", icon: "🍊", architecture: "perennial" },
    { code: "fig", nameAr: "تين (Fig)", icon: "🌳", architecture: "perennial" },
    { code: "almond", nameAr: "لوز (Almond)", icon: "🥜", architecture: "nut" },
    { code: "pomegranate", nameAr: "رمان (Pomegranate)", icon: "🍎", architecture: "perennial" },
    { code: "apricot", nameAr: "مشمش (Apricot)", icon: "🍑", architecture: "perennial" },
    { code: "watermelon", nameAr: "بطيخ (Watermelon)", icon: "🍉", architecture: "cucurbit" },
    { code: "melon", nameAr: "شمام (Melon)", icon: "🍈", architecture: "cucurbit" },
    { code: "onion", nameAr: "بصل (Onion)", icon: "🧅", architecture: "allium" },
    { code: "garlic", nameAr: "ثوم (Garlic)", icon: "🧄", architecture: "allium" },
    { code: "carrot", nameAr: "جزر (Carrot)", icon: "🥕", architecture: "root_tuber" },
    { code: "chickpea", nameAr: "حمص (Chickpea)", icon: "🫘", architecture: "legume" },
    { code: "lentil", nameAr: "عدس (Lentil)", icon: "🫘", architecture: "legume" },
    { code: "fava_bean", nameAr: "فول (Fava Bean)", icon: "🫘", architecture: "legume" },
    { code: "peanut", nameAr: "فول سوداني (Peanut)", icon: "🥜", architecture: "legume" },
    { code: "soybean", nameAr: "فول الصويا (Soybean)", icon: "🫘", architecture: "legume" },
    { code: "cotton", nameAr: "قطن (Cotton)", icon: "🧵", architecture: "cotton" },
    { code: "sunflower", nameAr: "عباد الشمس (Sunflower)", icon: "🌻", architecture: "oilseed" },
    { code: "canola", nameAr: "كانولا (Canola)", icon: "🌻", architecture: "oilseed" },
    { code: "sugarcane", nameAr: "قصب السكر (Sugarcane)", icon: "🍬", architecture: "sugar" },
    { code: "sugar_beet", nameAr: "بنجر السكر (Sugar Beet)", icon: "🍬", architecture: "sugar" },
    { code: "coffee", nameAr: "قهوة (Coffee)", icon: "☕", architecture: "stimulant" },
    { code: "tea", nameAr: "شاي (Tea)", icon: "🍵", architecture: "stimulant" },
    { code: "banana", nameAr: "موز (Banana)", icon: "🍌", architecture: "tropical_fruit" },
    { code: "mango", nameAr: "مانجو (Mango)", icon: "🥭", architecture: "tropical_tree" },
    { code: "avocado", nameAr: "أفوكادو (Avocado)", icon: "🥑", architecture: "tropical_tree" },
    { code: "cocoa", nameAr: "كاكاو (Cocoa)", icon: "🍫", architecture: "tropical_tree" },
    { code: "rubber", nameAr: "مطاط (Rubber)", icon: "🌳", architecture: "tropical_tree" },
    { code: "oil_palm", nameAr: "نخيل الزيت (Oil Palm)", icon: "🌴", architecture: "tropical_tree" },
  ];

  return NextResponse.json({ success: true, crops, count: crops.length, source: "fallback" });
}
