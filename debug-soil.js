
async function fetchSoilGridsData(lat, lng) {
    try {
        const props = ['clay', 'sand', 'silt', 'phh2o', 'soc', 'bdod', 'cec'];
        const params = new URLSearchParams({
            lat: lat.toString(),
            lon: lng.toString(),
        });
        props.forEach(p => params.append('property', p));
        params.append('depth', '0-5cm');
        params.append('depth', '5-15cm');
        params.append('depth', '15-30cm');
        params.append('value', 'mean');

        const url = `https://rest.isric.org/soilgrids/v2.0/properties/query?${params.toString()}`;
        console.log(`[SoilGrids] Fetching: ${url}`);

        const response = await fetch(url);
        if (!response.ok) {
            console.log(`Error: ${response.status}`);
            return;
        }

        const json = await response.json();
        // console.log("JSON:", JSON.stringify(json, null, 2)); 
        
        if (json.properties && json.properties.layers) {
            json.properties.layers.forEach(l => {
                console.log(`Layer: ${l.name}`);
                l.depths.forEach(d => {
                     console.log(`  Depth: ${d.label}, Mean: ${d.values.mean}`);
                });
            });
        } else {
             console.log("No layers found or different structure.");
        }

    } catch (error) {
        console.error("Failed:", error);
    }
}

// Test with Inland Algeria coordinates
fetchSoilGridsData(36.0, 3.0);
