
const fs = require('fs');
const path = require('path');

// Manually load .env since dotenv might not be installed
try {
    const envPath = path.resolve(__dirname, '.env');
    if (fs.existsSync(envPath)) {
        const envConfig = fs.readFileSync(envPath, 'utf8');
        envConfig.split('\n').forEach(line => {
            const [key, value] = line.split('=');
            if (key && value) {
                process.env[key.trim()] = value.trim().replace(/"/g, ''); 
            }
        });
        console.log("Loaded .env file manually.");
    }
} catch (e) {
    console.error("Could not load .env file", e);
}

const clientId = process.env.SENTINEL_CLIENT_ID;
const clientSecret = process.env.SENTINEL_CLIENT_SECRET;

async function getAccessToken() {
  const body = new URLSearchParams({
    grant_type: "client_credentials",
    client_id: clientId,
    client_secret: clientSecret,
  });

  const response = await fetch("https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString(),
  });

  const data = await response.json();
  if (!response.ok) throw new Error(JSON.stringify(data));
  return data.access_token;
}

async function verifyData() {
    try {
        console.log("Authenticating...");
        const token = await getAccessToken();
        console.log("Authenticated.");

        const bbox = [2.9066 - 0.0001, 36.5528 - 0.0001, 2.9066 + 0.0001, 36.5528 + 0.0001]; // Tiny point bbox
        const date = "2026-01-18";

        console.log(`Fetching data for ${date} at [${bbox.join(', ')}]...`);

        const evalscript = "//VERSION=3\n" +
        "function setup() {\n" +
        "  return {\n" +
        "    input: [\"B04\", \"B08\", \"dataMask\"],\n" +
        "    output: [{ id: \"default\", bands: 2, sampleType: \"FLOAT32\" }]\n" +
        "  };\n" +
        "}\n" +
        "function evaluatePixel(sample) {\n" +
        "  return {\n" +
        "    default: [sample.B04, sample.B08]\n" +
        "  };\n" +
        "}";

        const response = await fetch("https://sh.dataspace.copernicus.eu/api/v1/process", {
            method: "POST",
            headers: {
                Authorization: `Bearer ${token}`,
                "Content-Type": "application/json",
                Accept: "application/json", // Request JSON output for raw values
            },
            body: JSON.stringify({
                input: {
                    bounds: {
                        bbox: bbox,
                        properties: { crs: "http://www.opengis.net/def/crs/EPSG/0/4326" }
                    },
                    data: [{
                        type: "sentinel-2-l2a",
                        timeRange: { from: `${date}T00:00:00Z`, to: `${date}T23:59:59Z` }
                    }]
                },
                output: {
                    width: 1,
                    height: 1,
                    responses: [{ identifier: "default", format: { type: "application/json" } }]
                },
                evalscript: evalscript
            })
        });

        if (!response.ok) {
            const errText = await response.text();
            fs.writeFileSync('sentinel_error.txt', errText);
            console.error("API Error written to sentinel_error.txt");
            return;
        }

        const data = await response.json();
        fs.writeFileSync('sentinel_result.json', JSON.stringify(data, null, 2));
        console.log("Success! Data written to sentinel_result.json");
        
    } catch (e) {
        fs.writeFileSync('sentinel_error.txt', e.stack || e.toString());
        console.error("Script Error written to sentinel_error.txt");
    }
}
verifyData();
