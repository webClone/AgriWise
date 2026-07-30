export type SceneProfile = "truth" | "agro" | "analysis" | "inspection";

// MapLibre configuration profiles

export const SCENE_PROVIDERS: Record<SceneProfile, object> = {
  // Esri World Imagery - Good standard context
  truth: {
    version: 8,
    sources: {
      "esri-imagery": {
        type: "raster" as const,
        tiles: [
          "/api/map/tiles/esri/{z}/{y}/{x}"
        ],
        tileSize: 256,
        attribution: "Tiles &copy; Esri"
      }
    },
    layers: [
      {
        id: "esri-imagery-layer",
        type: "raster" as const,
        source: "esri-imagery",
        minzoom: 0,
        maxzoom: 22
      }
    ]
  },
  
  // Future: Could be a false-color or specific agro basemap
  agro: {
    version: 8,
    sources: {
      "esri-imagery": {
        type: "raster" as const,
        tiles: [
          "/api/map/tiles/esri/{z}/{y}/{x}"
        ],
        tileSize: 256,
        attribution: "Tiles &copy; Esri"
      }
    },
    layers: [
      {
        id: "esri-imagery-layer",
        type: "raster" as const,
        source: "esri-imagery",
        minzoom: 0,
        maxzoom: 22,
        paint: {
            "raster-contrast": 0.4, // Slight contrast bump for agro inspection
            "raster-saturation": 0.4
        }
      }
    ]
  },

  // Analysis mode: same basemap, zero filters — default provider colors
  analysis: {
    version: 8,
    sources: {
      "esri-imagery": {
        type: "raster" as const,
        tiles: [
          "/api/map/tiles/esri/{z}/{y}/{x}"
        ],
        tileSize: 256,
        attribution: "Tiles &copy; Esri"
      }
    },
    layers: [
      {
        id: "esri-imagery-layer",
        type: "raster" as const,
        source: "esri-imagery",
        minzoom: 0,
        maxzoom: 24
      }
    ]
  },

  // Future: Planet or high-res drone lookup
  inspection: {
    version: 8,
    sources: {
      "esri-imagery": {
        type: "raster" as const,
        tiles: [
          "/api/map/tiles/esri/{z}/{y}/{x}"
        ],
        tileSize: 256,
        attribution: "Tiles &copy; Esri"
      }
    },
    layers: [
      {
        id: "esri-imagery-layer",
        type: "raster" as const,
        source: "esri-imagery",
        minzoom: 0,
        maxzoom: 24
      }
    ]
  }
};

export function getDynamicStyle(tileUrl: string, attribution: string = "Tiles &copy; AgriBrain Open Basemap"): any {
  return {
    version: 8,
    sources: {
      "esri-imagery": {
        type: "raster" as const,
        tiles: [
          "/api/map/tiles/esri/{z}/{y}/{x}"
        ],
        tileSize: 256,
        attribution: "Tiles &copy; Esri"
      },
      "dynamic-imagery": {
        type: "raster",
        tiles: [tileUrl],
        tileSize: 256,
        attribution: attribution
      }
    },
    layers: [
      {
        id: "esri-imagery-layer",
        type: "raster" as const,
        source: "esri-imagery",
        minzoom: 0,
        maxzoom: 22
      },
      {
        id: "dynamic-imagery-layer",
        type: "raster",
        source: "dynamic-imagery",
        minzoom: 0,
        maxzoom: 24
      }
    ]
  };
}
