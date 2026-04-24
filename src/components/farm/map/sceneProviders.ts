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
          "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
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
          "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
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
            "raster-contrast": 0.1, // Slight contrast bump for agro inspection
            "raster-saturation": 0.2
        }
      }
    ]
  },

  // Analysis mode: dim + desaturate basemap so overlays dominate
  analysis: {
    version: 8,
    sources: {
      "esri-imagery": {
        type: "raster" as const,
        tiles: [
          "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
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
            "raster-brightness-min": 0.35,
            "raster-brightness-max": 0.85,
            "raster-saturation": -0.15,
            "raster-contrast": 0.10
        }
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
          "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
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
  }
};
