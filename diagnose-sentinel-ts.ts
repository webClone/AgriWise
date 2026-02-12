import { getAccessToken, EVALSCRIPTS, fetchSentinelImage } from '@/lib/satellite-providers/sentinel-service';
import dotenv from 'dotenv';
dotenv.config();

async function test() {
  console.log("Testing Sentinel Hub Auth...");
  try {
    const token = await getAccessToken();
    console.log("Token acquired successfully!");
    if (!token) console.error("TOKEN IS EMPTY/NULL");
    else console.log("Token starts with:", token.substring(0, 10));
    
    console.log("Testing Process API (NDVI)...");
    const bbox = [2.7, 36.4, 2.8, 36.5];
    const date = "2024-06-01"; 
    
    // Explicitly using 'ndvi'
    const imgData = await fetchSentinelImage(bbox, date, 'ndvi');
    
    if (imgData && imgData.startsWith('data:image/png')) {
        console.log("Fetch Sentinel Image (NDVI) SUCCESS! Size: " + imgData.length);
    } else {
        console.error("Fetch Sentinel Image (NDVI) FAILED (returned empty string)");
    }

  } catch (err: any) {
    console.error("DIAGNOSTIC CRASH:", err.message);
    if (err.cause) console.error("Cause:", err.cause);
  }
}

test();
