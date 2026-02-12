
import { NextResponse } from "next/server";

// GET /api/crops - List available crops
export async function GET() {
  // In a real app, this could query the DB for distinct cropCodes used in CropCycles
  // For now, we return a comprehensive list of popular crops in Algeria
  const crops = [
    { code: "wheat", nameAr: "قمح (Wheat)", icon: "🌾" },
    { code: "barley", nameAr: "شعير (Barley)", icon: "🌾" },
    { code: "potato", nameAr: "بطاطا (Potato)", icon: "🥔" },
    { code: "tomato", nameAr: "طماطم (Tomato)", icon: "🍅" },
    { code: "olive", nameAr: "زيتون (Olive)", icon: "🫒" },
    { code: "date_palm", nameAr: "نخيل التمر (Date Palm)", icon: "🌴" },
    { code: "onion", nameAr: "بصل (Onion)", icon: "🧅" },
    { code: "garlic", nameAr: "ثوم (Garlic)", icon: "🧄" },
    { code: "carrot", nameAr: "جزر (Carrot)", icon: "🥕" },
    { code: "pepper", nameAr: "فلفل (Pepper)", icon: "🌶️" },
    { code: "watermelon", nameAr: "بطيخ (Watermelon)", icon: "🍉" },
    { code: "melon", nameAr: "شمام (Melon)", icon: "🍈" },
    { code: "grape", nameAr: "عنب (Grape)", icon: "🍇" },
    { code: "citrus", nameAr: "حمضيات (Citrus)", icon: "🍊" },
    { code: "fig", nameAr: "تين (Fig)", icon: "🌳" },
    { code: "apricot", nameAr: "مشمش (Apricot)", icon: "🍑" },
    { code: "almond", nameAr: "لوز (Almond)", icon: "🥜" },
    { code: "maize", nameAr: "ذرة (Maize)", icon: "🌽" },
    { code: "fava_bean", nameAr: "فول (Fava Bean)", icon: "🫘" },
    { code: "chickpea", nameAr: "حمص (Chickpea)", icon: "🥘" },
  ];

  return NextResponse.json({ success: true, crops });
}
