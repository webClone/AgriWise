
import { getAccessToken, EVALSCRIPTS } from "./src/lib/satellite-providers/sentinel-service";
import * as fs from 'node:fs';

async function diagnose() {
  const log = (msg: string) => { console.log(msg); fs.appendFileSync('diag.log', msg + '\n'); };
  if (fs.existsSync('diag.log')) fs.unlinkSync('diag.log');

  log("--- Sentinel Hub Deep Diagnostic (Flat Structure) ---");
  try {
    const token = await getAccessToken();
    log("✅ Token Success");

    const bbox = [2.7, 36.4, 2.8, 36.5]; 
    const date = "2025-06-01"; 
    
    log("Testing Process API...");
    const response = await fetch("https://sh.dataspace.copernicus.eu/api/v1/process", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        Accept: "image/png",
      },
      body: JSON.stringify({
        input: {
          bounds: { bbox, properties: { crs: "http://www.opengis.net/def/crs/EPSG/0/4326" } },
          data: [{ 
            dataCollection: "SENTINEL2_L2A", 
            timeRange: { from: `${date}T00:00:00Z`, to: `${date}T23:59:59Z` } 
          }],
        },
        output: { width: 512, height: 512, responses: [{ identifier: "default", format: { type: "image/png" } }] },
        evalscript: EVALSCRIPTS['ndvi'],
      }),
    });

    if (response.ok) {
      log("✅ Process API Success!");
    } else {
      const errorText = await response.text();
      log("❌ Process API Failed: " + response.status);
      log("Error Body: " + errorText);
    }

  } catch (error) {
    log("💥 DIAGNOSTIC CRASH: " + (error as Error).message);
  }
}

diagnose();
