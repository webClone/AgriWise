/**
 * Utility functions for satellite data processing and visualization
 */

export interface RasterPixel {
    bounds: [[number, number], [number, number]];
    color: string;
    value: number;
}

export function calculateZones(val: number): { high: number; medium: number; low: number } {
  // val is typically NDVI, NDMI, or EVI (0 to 1)
  if (val > 0.6) return { high: 60, medium: 30, low: 10 };
  if (val > 0.4) return { high: 40, medium: 40, low: 20 };
  return { high: 20, medium: 40, low: 40 };
}

/**
 * Returns a color hex code based on the metric type and value (0-1)
 * Optimized for professional agriculture heatmaps (Green = Health, Red = Stress)
 */
export function getMetricColor(metric: string, value: number): string {
    const m = metric.toLowerCase();
    
    // MOISTURE INDEX (Blue Scale)
    if (m === 'ndmi' || m === 'moisture-index') {
        if (value <= 0.2) return "#f8fafc"; // Very Dry (White/Slated)
        if (value <= 0.3) return "#bae6fd"; // Dry
        if (value <= 0.5) return "#38bdf8"; // Moderate
        if (value <= 0.7) return "#0284c7"; // Moist
        return "#1e3a8a"; // Very Moist (Deep Blue)
    }

    // VEGETATION INDICES (Green-Yellow-Red Scale)
    // Professional NDVI scale: < 0.2 is barren/stressed, > 0.6 is healthy
    if (value <= 0.2) return "#7f1d1d"; // Dead/Barren (Deep Red)
    if (value <= 0.3) return "#dc2626"; // High Stress (Red)
    if (value <= 0.4) return "#f59e0b"; // Warning (Orange)
    if (value <= 0.5) return "#facc15"; // Emerging (Yellow)
    if (value <= 0.6) return "#a3e635"; // Healthy (Light Green)
    if (value <= 0.8) return "#16a34a"; // Vibrant (Green)
    return "#064e3b"; // Peak Vigor (Deep Forest Green)
}

/**
 * Generates a mock grid of "pixels" within a GeoJSON boundary for simulation mode.
 * Provides the "Digital Twin" aesthetic with high resolution.
 */
export function generateRasterGrid(geoJson: any, metric: string, avgValue?: number): RasterPixel[] {
    if (!geoJson || !geoJson.geometry) return [];
    
    try {
        let coords = geoJson.geometry.coordinates[0];
        while (Array.isArray(coords[0]) && Array.isArray(coords[0][0])) {
            coords = coords[0];
        }

        let minLat = 90, maxLat = -90, minLng = 180, maxLng = -180;
        
        coords.forEach((coord: any) => {
            const [lng, lat] = coord;
            if (lat < minLat) minLat = lat;
            if (lat > maxLat) maxLat = lat;
            if (lng < minLng) minLng = lng;
            if (lng > maxLng) maxLng = lng;
        });

        // Increase grid size for more "dense" heatmap look (20x20 = 400 pixels)
        const gridSize = 20;
        const latStep = (maxLat - minLat) / gridSize;
        const lngStep = (maxLng - minLng) / gridSize;
        
        const pixels: RasterPixel[] = [];
        
        for (let i = 0; i < gridSize; i++) {
            for (let j = 0; j < gridSize; j++) {
                const cellMinLat = minLat + (i * latStep);
                const cellMaxLat = cellMinLat + latStep;
                const cellMinLng = minLng + (j * lngStep);
                const cellMaxLng = cellMinLng + lngStep;

                const baseValue = avgValue || 0.5;
                const noise = (Math.sin(i * 0.5) * Math.cos(j * 0.5) * 0.2); 
                const randomness = (Math.random() * 0.2) - 0.1;
                const value = Math.max(0.1, Math.min(0.9, baseValue + noise + randomness));
                
                pixels.push({
                    bounds: [
                        [cellMinLat, cellMinLng],
                        [cellMaxLat, cellMaxLng]
                    ],
                    color: getMetricColor(metric, value),
                    value: value
                });
            }
        }
        
        return pixels;
    } catch (e) {
        console.error("Error generating raster grid:", e);
        return [];
    }
}
