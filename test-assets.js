
const NASA_EARTH_ASSETS_URL = "https://api.nasa.gov/planetary/earth/assets";
const NASA_API_KEY = "JthSNH4d7ePsNueRfNgQ4JEu4FbfCGzGhRnHhPh8";
const LAT = 36.5528;
const LNG = 2.9066;

async function testAssets() {
    console.log("Testing Assets with Key:", NASA_API_KEY.slice(0, 5) + "...");
    const url = `${NASA_EARTH_ASSETS_URL}?lon=${LNG}&lat=${LAT}&begin=2025-01-01&api_key=${NASA_API_KEY}`;
    console.log("URL:", url);
    
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);

    try {
        const res = await fetch(url, { signal: controller.signal });
        console.log("Status:", res.status);
        const data = await res.json();
        console.log("Count:", (data.results || []).length);
    } catch (e) {
        console.error("Error:", e.name === 'AbortError' ? 'Timed out after 10s' : e.message);
    } finally {
        clearTimeout(timeout);
    }
}

testAssets();
