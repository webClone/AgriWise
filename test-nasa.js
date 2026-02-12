
const NASA_POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point";
const NASA_EARTH_ASSETS_URL = "https://api.nasa.gov/planetary/earth/assets";
const NASA_API_KEY = "JthSNH4d7ePsNueRfNgQ4JEu4FbfCGzGhRnHhPh8";
const LAT = 36.5528;
const LNG = 2.9066;

async function testNASA() {
    console.log("=== Testing NASA POWER ===");
    const endDate = "20260129"; 
    const startDate = "20251101";
    const powerUrl = `${NASA_POWER_URL}?parameters=T2M&community=AG&longitude=${LNG}&latitude=${LAT}&start=${startDate}&end=${endDate}&format=JSON`;
    
    try {
        const res = await fetch(powerUrl);
        console.log("POWER Status:", res.status);
        const data = await res.json();
        console.log("POWER Data Sample (T2M):", Object.keys(data.properties?.parameter?.T2M || {}).length, "dates found");
    } catch (e) {
        console.error("POWER Error:", e.message);
    }

    console.log("\n=== Testing NASA EARTH ASSETS ===");
    const assetsUrl = `${NASA_EARTH_ASSETS_URL}?lon=${LNG}&lat=${LAT}&begin=2025-01-01&api_key=${NASA_API_KEY}`;
    try {
        const res = await fetch(assetsUrl);
        console.log("ASSETS Status:", res.status);
        const data = await res.json();
        console.log("ASSETS Count:", (data.results || []).length);
        if (data.results && data.results.length > 0) {
            console.log("Latest Asset Date:", data.results[data.results.length-1].date);
        }
    } catch (e) {
        console.error("ASSETS Error:", e.message);
    }
}

testNASA();
