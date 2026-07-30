"""
Environmental Context Engine V1.

Provides trusted soil priors, weather forcing, and environmental context
for AgriBrain's Layer 0 state estimation pipeline.

Sources:
  - SoilGrids (ISRIC): fine global soil property prior (250 m)
  - FAO/HWSD: coarse soil/ecological fallback and classification (~1 km)
  - Open-Meteo: primary ag-weather + ET₀ provider
  - OpenWeather: current/forecast cross-check and redundancy
"""
