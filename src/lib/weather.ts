// Weather API Integration using Open-Meteo (Free, no API key required)
// https://open-meteo.com/

interface WeatherData {
  location: {
    latitude: number;
    longitude: number;
    wilaya: string;
  };
  current: {
    temperature: number;
    humidity: number;
    windSpeed: number;
    weatherCode: number;
    condition: string;
    conditionAr: string;
    icon: string;
  };
  daily: {
    date: string;
    tempMax: number;
    tempMin: number;
    weatherCode: number;
    condition: string;
    conditionAr: string;
    icon: string;
    precipitationProbability: number;
    uvIndex: number;
  }[];
  alerts: {
    type: string;
    severity: "info" | "warning" | "critical";
    message: string;
    messageAr: string;
    icon: string;
  }[];
}

// Weather code to condition mapping
const weatherConditions: Record<number, { en: string; ar: string; icon: string }> = {
  0: { en: "Clear sky", ar: "صافٍ", icon: "☀️" },
  1: { en: "Mainly clear", ar: "صافٍ غالباً", icon: "🌤️" },
  2: { en: "Partly cloudy", ar: "غائم جزئياً", icon: "⛅" },
  3: { en: "Overcast", ar: "غائم", icon: "☁️" },
  45: { en: "Fog", ar: "ضباب", icon: "🌫️" },
  48: { en: "Depositing rime fog", ar: "ضباب متجمد", icon: "🌫️" },
  51: { en: "Light drizzle", ar: "رذاذ خفيف", icon: "🌧️" },
  53: { en: "Moderate drizzle", ar: "رذاذ معتدل", icon: "🌧️" },
  55: { en: "Dense drizzle", ar: "رذاذ كثيف", icon: "🌧️" },
  61: { en: "Slight rain", ar: "مطر خفيف", icon: "🌧️" },
  63: { en: "Moderate rain", ar: "مطر معتدل", icon: "🌧️" },
  65: { en: "Heavy rain", ar: "مطر غزير", icon: "🌧️" },
  66: { en: "Light freezing rain", ar: "مطر متجمد خفيف", icon: "🌨️" },
  67: { en: "Heavy freezing rain", ar: "مطر متجمد غزير", icon: "🌨️" },
  71: { en: "Slight snow", ar: "ثلج خفيف", icon: "🌨️" },
  73: { en: "Moderate snow", ar: "ثلج معتدل", icon: "🌨️" },
  75: { en: "Heavy snow", ar: "ثلج كثيف", icon: "🌨️" },
  77: { en: "Snow grains", ar: "حبيبات ثلجية", icon: "🌨️" },
  80: { en: "Slight rain showers", ar: "زخات مطر خفيفة", icon: "🌦️" },
  81: { en: "Moderate rain showers", ar: "زخات مطر معتدلة", icon: "🌦️" },
  82: { en: "Violent rain showers", ar: "زخات مطر عنيفة", icon: "⛈️" },
  85: { en: "Slight snow showers", ar: "زخات ثلج خفيفة", icon: "🌨️" },
  86: { en: "Heavy snow showers", ar: "زخات ثلج كثيفة", icon: "🌨️" },
  95: { en: "Thunderstorm", ar: "عاصفة رعدية", icon: "⛈️" },
  96: { en: "Thunderstorm with hail", ar: "عاصفة رعدية مع برد", icon: "⛈️" },
  99: { en: "Thunderstorm with heavy hail", ar: "عاصفة رعدية مع برد كثيف", icon: "⛈️" },
};

function getWeatherCondition(code: number) {
  return weatherConditions[code] || { en: "Unknown", ar: "غير معروف", icon: "❓" };
}

// Wilaya coordinates for weather lookup
export const wilayaCoordinates: Record<string, { lat: number; lng: number; name: string; nameAr: string }> = {
  "01": { lat: 36.7538, lng: 3.0588, name: "Adrar", nameAr: "أدرار" },
  "02": { lat: 35.9311, lng: 0.0842, name: "Chlef", nameAr: "الشلف" },
  "03": { lat: 33.8000, lng: 2.8833, name: "Laghouat", nameAr: "الأغواط" },
  "04": { lat: 35.4000, lng: 7.7500, name: "Oum El Bouaghi", nameAr: "أم البواقي" },
  "05": { lat: 35.5550, lng: 6.1742, name: "Batna", nameAr: "باتنة" },
  "06": { lat: 36.4794, lng: 2.8278, name: "Béjaïa", nameAr: "بجاية" },
  "07": { lat: 34.8500, lng: 5.7333, name: "Biskra", nameAr: "بسكرة" },
  "08": { lat: 34.8481, lng: -1.3522, name: "Bechar", nameAr: "بشار" },
  "09": { lat: 36.4167, lng: 3.2500, name: "Blida", nameAr: "البليدة" },
  "10": { lat: 36.7525, lng: 5.0833, name: "Bouira", nameAr: "البويرة" },
  "11": { lat: 23.0000, lng: 5.0833, name: "Tamanrasset", nameAr: "تمنراست" },
  "12": { lat: 35.4056, lng: 8.1167, name: "Tébessa", nameAr: "تبسة" },
  "13": { lat: 34.8667, lng: -1.3000, name: "Tlemcen", nameAr: "تلمسان" },
  "14": { lat: 35.1667, lng: 1.2500, name: "Tiaret", nameAr: "تيارت" },
  "15": { lat: 36.7736, lng: 4.0667, name: "Tizi Ouzou", nameAr: "تيزي وزو" },
  "16": { lat: 36.7538, lng: 3.0588, name: "Algiers", nameAr: "الجزائر" },
  "17": { lat: 34.6667, lng: 3.2500, name: "Djelfa", nameAr: "الجلفة" },
  "18": { lat: 36.2500, lng: 6.6000, name: "Jijel", nameAr: "جيجل" },
  "19": { lat: 36.2667, lng: 2.7500, name: "Sétif", nameAr: "سطيف" },
  "20": { lat: 35.5500, lng: 0.6333, name: "Saida", nameAr: "سعيدة" },
  "21": { lat: 36.9000, lng: 7.7667, name: "Skikda", nameAr: "سكيكدة" },
  "22": { lat: 35.2000, lng: -0.6333, name: "Sidi Bel Abbes", nameAr: "سيدي بلعباس" },
  "23": { lat: 36.8667, lng: 7.1167, name: "Annaba", nameAr: "عنابة" },
  "24": { lat: 36.4667, lng: 7.4333, name: "Guelma", nameAr: "قالمة" },
  "25": { lat: 36.4572, lng: 6.2661, name: "Constantine", nameAr: "قسنطينة" },
  "26": { lat: 36.2667, lng: 2.8833, name: "Médéa", nameAr: "المدية" },
  "27": { lat: 35.9333, lng: -0.0833, name: "Mostaganem", nameAr: "مستغانم" },
  "28": { lat: 34.8833, lng: 0.2833, name: "M'Sila", nameAr: "المسيلة" },
  "29": { lat: 35.6667, lng: 0.0833, name: "Mascara", nameAr: "معسكر" },
  "30": { lat: 31.9500, lng: 5.3167, name: "Ouargla", nameAr: "ورقلة" },
  "31": { lat: 35.6969, lng: -0.6331, name: "Oran", nameAr: "وهران" },
  "32": { lat: 33.3639, lng: 6.8667, name: "El Bayadh", nameAr: "البيض" },
  "33": { lat: 28.0456, lng: -1.0583, name: "Illizi", nameAr: "إليزي" },
  "34": { lat: 36.0667, lng: 4.6333, name: "Bordj Bou Arreridj", nameAr: "برج بوعريريج" },
  "35": { lat: 36.7500, lng: 3.4667, name: "Boumerdes", nameAr: "بومرداس" },
  "36": { lat: 36.7539, lng: 7.0867, name: "El Tarf", nameAr: "الطارف" },
  "37": { lat: 26.5000, lng: 8.0000, name: "Tindouf", nameAr: "تندوف" },
  "38": { lat: 35.0500, lng: 2.8833, name: "Tissemsilt", nameAr: "تيسمسيلت" },
  "39": { lat: 32.4833, lng: 3.6667, name: "El Oued", nameAr: "الوادي" },
  "40": { lat: 35.3667, lng: 1.5333, name: "Khenchela", nameAr: "خنشلة" },
  "41": { lat: 36.2667, lng: 7.9500, name: "Souk Ahras", nameAr: "سوق أهراس" },
  "42": { lat: 36.1833, lng: 5.4167, name: "Tipaza", nameAr: "تيبازة" },
  "43": { lat: 36.1167, lng: 6.5667, name: "Mila", nameAr: "ميلة" },
  "44": { lat: 36.2639, lng: 2.2500, name: "Aïn Defla", nameAr: "عين الدفلى" },
  "45": { lat: 35.9333, lng: -0.9333, name: "Naâma", nameAr: "النعامة" },
  "46": { lat: 35.7333, lng: -0.5500, name: "Aïn Témouchent", nameAr: "عين تموشنت" },
  "47": { lat: 32.5000, lng: 3.6833, name: "Ghardaia", nameAr: "غرداية" },
  "48": { lat: 35.7167, lng: 0.8833, name: "Relizane", nameAr: "غليزان" },
  // New wilayas (2019)
  "49": { lat: 27.6833, lng: 8.1500, name: "El M'Ghair", nameAr: "المغير" },
  "50": { lat: 27.8667, lng: 9.4667, name: "El Menia", nameAr: "المنيعة" },
  "51": { lat: 33.0667, lng: 6.0667, name: "Ouled Djellal", nameAr: "أولاد جلال" },
  "52": { lat: 25.3000, lng: 0.2833, name: "Bordj Baji Mokhtar", nameAr: "برج باجي مختار" },
  "53": { lat: 28.3500, lng: 2.1667, name: "Béni Abbès", nameAr: "بني عباس" },
  "54": { lat: 29.2500, lng: 0.3000, name: "Timimoun", nameAr: "تيميمون" },
  "55": { lat: 31.0167, lng: 6.8667, name: "Touggourt", nameAr: "تقرت" },
  "56": { lat: 26.3167, lng: 9.4833, name: "Djanet", nameAr: "جانت" },
  "57": { lat: 24.5667, lng: 9.4833, name: "In Salah", nameAr: "عين صالح" },
  "58": { lat: 19.5667, lng: 9.4500, name: "In Guezzam", nameAr: "عين قزام" },
};

export async function fetchWeather(wilayaCode: string): Promise<WeatherData | null> {
  const coords = wilayaCoordinates[wilayaCode];
  if (!coords) {
    console.error(`Unknown wilaya code: ${wilayaCode}`);
    return null;
  }

  try {
    const url = `https://api.open-meteo.com/v1/forecast?latitude=${coords.lat}&longitude=${coords.lng}&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,uv_index_max&timezone=Africa%2FAlgiers&forecast_days=7`;
    
    const response = await fetch(url, { next: { revalidate: 1800 } }); // Cache for 30 min
    
    if (!response.ok) {
      throw new Error(`Weather API error: ${response.status}`);
    }
    
    const data = await response.json();
    
    const currentCondition = getWeatherCondition(data.current.weather_code);
    
    const weather: WeatherData = {
      location: {
        latitude: coords.lat,
        longitude: coords.lng,
        wilaya: coords.nameAr,
      },
      current: {
        temperature: Math.round(data.current.temperature_2m),
        humidity: data.current.relative_humidity_2m,
        windSpeed: Math.round(data.current.wind_speed_10m),
        weatherCode: data.current.weather_code,
        condition: currentCondition.en,
        conditionAr: currentCondition.ar,
        icon: currentCondition.icon,
      },
      daily: data.daily.time.map((date: string, i: number) => {
        const condition = getWeatherCondition(data.daily.weather_code[i]);
        return {
          date,
          tempMax: Math.round(data.daily.temperature_2m_max[i]),
          tempMin: Math.round(data.daily.temperature_2m_min[i]),
          weatherCode: data.daily.weather_code[i],
          condition: condition.en,
          conditionAr: condition.ar,
          icon: condition.icon,
          precipitationProbability: data.daily.precipitation_probability_max[i] || 0,
          uvIndex: Math.round(data.daily.uv_index_max[i] || 0),
        };
      }),
      alerts: [],
    };
    
    // Generate agricultural alerts based on weather
    weather.alerts = generateWeatherAlerts(weather);
    
    return weather;
  } catch (error) {
    console.error("Error fetching weather:", error);
    return null;
  }
}

function generateWeatherAlerts(weather: WeatherData): WeatherData["alerts"] {
  const alerts: WeatherData["alerts"] = [];
  
  // Check for frost risk (temp below 4°C in next 3 days)
  for (let i = 0; i < Math.min(3, weather.daily.length); i++) {
    if (weather.daily[i].tempMin <= 4) {
      alerts.push({
        type: "frost",
        severity: weather.daily[i].tempMin <= 0 ? "critical" : "warning",
        message: `Expected low of ${weather.daily[i].tempMin}°C. Protect sensitive seedlings.`,
        messageAr: `توقع انخفاض الحرارة إلى ${weather.daily[i].tempMin}°. يُنصح بحماية الشتلات الحساسة.`,
        icon: "❄️",
      });
      break;
    }
  }
  
  // Check for heat wave (temp above 40°C)
  for (let i = 0; i < Math.min(3, weather.daily.length); i++) {
    if (weather.daily[i].tempMax >= 40) {
      alerts.push({
        type: "heat",
        severity: weather.daily[i].tempMax >= 45 ? "critical" : "warning",
        message: `Expected high of ${weather.daily[i].tempMax}°C. Increase irrigation and provide shade.`,
        messageAr: `توقع ارتفاع الحرارة إلى ${weather.daily[i].tempMax}°. زد الري ووفر الظل للمحاصيل.`,
        icon: "🥵",
      });
      break;
    }
  }
  
  // Check for rain opportunity
  for (let i = 0; i < Math.min(3, weather.daily.length); i++) {
    if (weather.daily[i].precipitationProbability >= 60) {
      alerts.push({
        type: "rain",
        severity: "info",
        message: `Rain expected (${weather.daily[i].precipitationProbability}% chance). Consider delaying irrigation.`,
        messageAr: `أمطار متوقعة (${weather.daily[i].precipitationProbability}% احتمال). يمكن تأجيل الري.`,
        icon: "🌧️",
      });
      break;
    }
  }
  
  // Check for strong wind
  if (weather.current.windSpeed >= 40) {
    alerts.push({
      type: "wind",
      severity: weather.current.windSpeed >= 60 ? "critical" : "warning",
      message: `Strong winds at ${weather.current.windSpeed} km/h. Secure structures and delay spraying.`,
      messageAr: `رياح قوية بسرعة ${weather.current.windSpeed} كم/س. أمّن المنشآت وأجّل الرش.`,
      icon: "💨",
    });
  }
  
  return alerts;
}

export function formatArabicDate(date: string | Date): string {
  const d = new Date(date);
  const days = ["الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت"];
  const months = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"];
  
  return `${days[d.getDay()]}، ${d.getDate()} ${months[d.getMonth()]}`;
}
