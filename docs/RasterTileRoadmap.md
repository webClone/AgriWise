# Raster Tile Migration Architecture Roadmap

Currently, the AgriBrain layer (Phase 2E) generates semantic visual surfaces via **Client-Side Image Synthesis**. It fetches raw numeric 2D arrays (e.g., NDVI ranges from the Python L10 pipeline), uses a point-in-polygon ray casting mask, maps them to colors natively in JS, builds an `ImageData` object, and drapes it via Deck.gl's `BitmapLayer`.

While excellent for prototyping the "Intelligence Composition" visual grammar (Surface + Contour + Uncertainty Grid), this has performance and architectural ceilings:

1. **Payload Size**: Large plots at fine resolution will bloat the JSON payload.
2. **Main Thread Blocking**: Calculating pixel values, interpolating colors, and generating `ImageData` blocks the React UI thread on massive grids.
3. **No Progressive Loading**: The map has to download the entire array before rendering a single pixel, harming the "snappy" premium feel.

## Future State: Raster & Vector Tile Endpoints

To achieve true production-grade "Ag Operating System" performance, we will migrate from the current payload-draped arrays to standard OGC/MapLibre tiles dynamically served by the backend.

### 1. Tile Server (e.g. TiTiler or Custom FastAPI Rasterizer)

Instead of returning 2D arrays, the `/api/agribrain/surfaces` endpoint will return a `TileJSON` mapping to a dynamic tile server endpoint, such as `/api/tiles/surface/{z}/{x}/{y}.png`.
This tile server will:

- Read directly from the underlying Cloud Optimized GeoTIFFs (COGs) or NetCDF tensors.
- Mask to the field boundary on the GPU or via GDAL natively in Python.
- Synthesize the colormap based on statistical distribution requests (e.g., color map min/max clamped to P10/P90).

### 2. Frontend Layer Updates

- **SemanticSurfaceLayer** -> Switches from Deck.gl `BitmapLayer` to a Native Maplibre `raster` layer or Deck.gl `TileLayer` + `BitmapLayer` fetching XYZ tiles.
- **ContourSurfaceLayer** -> Contour extraction moves to the backend using GDAL Contour generation, piped to the frontend as Mapbox Vector Tiles (MVT).
- **UncertaintyGridLayer** -> Can remain a specialized Data overlay or become a 3D procedural mask, but MVT points marking conflict zones will scale exponentially better.

### Transition Plan

1. Stand up a Tile endpoint in Python (potentially using `rio-tiler` or `titiler`).
2. Add `tile_manifest` object into the L10 pipeline output that guides React to the XYZ endpoints.
3. Upgrade `PlotMapShell` to mount MapLibre `Source` and `Layer` pairs for dynamic surfaces, sunsetting the raw 2D array approach.
