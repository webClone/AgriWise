
const { getAccessToken, EVALSCRIPTS } = require('./src/lib/satellite-providers/sentinel-service');
const dotenv = require('dotenv');
dotenv.config();

async function test() {
  console.log("Testing Sentinel Hub Auth...");
  try {
    const token = await getAccessToken();
    console.log("Token acquired successfully (starts with):", token.substring(0, 10));
    
    console.log("Testing Process API with NDVI...");
    const bbox = [2.7, 36.4, 2.8, 36.5];
    const date = "2025-06-01";
    
    const response = await fetch("https://sh.dataspace.copernicus.eu/api/v1/process", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        Accept: "image/png",
      },
      body: JSON.stringify({
        input: {
          bounds: { bbox },
          data: [{ dataCollection: "SENTINEL2_L2A", dataFilter: { timeRange: { from: `${date}T00:00:00Z`, to: `${date}T23:59:59Z` } } }],
        },
        output: { width: 256, height: 256, responses: [{ identifier: "default", format: { type: "image/png" } }] },
        evalscript: EVALSCRIPTS['ndvi'],
      }),
    });

    if (response.ok) {
      console.log("Process API SUCCESS!");
    } else {
      console.error("Process API FAILED:", response.status, await response.text());
    }
  } catch (err) {
    console.error("DIAGNOSTIC CRASH:", err.message);
  }
}

test();
