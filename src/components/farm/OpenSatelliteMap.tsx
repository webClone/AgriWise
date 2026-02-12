"use client";

import React, { useEffect, useRef, useMemo } from 'react';
import 'ol/ol.css';
import Map from 'ol/Map';
import View from 'ol/View';
import TileLayer from 'ol/layer/Tile';
import VectorLayer from 'ol/layer/Vector';
import VectorSource from 'ol/source/Vector';
import XYZ from 'ol/source/XYZ';
import TileWMS from 'ol/source/TileWMS';
import GeoJSON from 'ol/format/GeoJSON';
import { fromLonLat } from 'ol/proj';
import { Style, Stroke, Fill } from 'ol/style';
import { RasterPixel } from "@/lib/satellite-providers/satellite-utils";
import { EVALSCRIPTS } from "@/lib/satellite-providers/sentinel-service";
import Feature from 'ol/Feature';
import Polygon from 'ol/geom/Polygon';
import { transform as olTransform } from 'ol/proj';

interface OpenSatelliteMapProps {
    lat: number;
    lng: number;
    geoJson?: any;
    metric?: string;
    imageUrl?: string;
    imageBounds?: [[number, number], [number, number]];
    interactive?: boolean;
    provider?: string;
    avgValue?: number;
    date?: string;
    rasterPixels?: RasterPixel[];
}

export default function OpenSatelliteMap({
    lat,
    lng,
    geoJson,
    metric = 'none',
    provider = 'openweather',
    date,
    rasterPixels = [],
    interactive = true
}: OpenSatelliteMapProps) {
    const mapElement = useRef<HTMLDivElement>(null);
    const mapRef = useRef<Map | null>(null);

    // Map UI Metric ID to official Sentinel Hub / CDSE Layer ID
    const wmsLayerId = useMemo(() => {
        switch(metric) {
            case 'none': return 'TRUE-COLOR';
            case 'false-color': return 'FALSE-COLOR';
            case 'ndvi': return 'NDVI';
            case 'evi': return 'EVI';
            case 'savi': return 'SAVI';
            case 'moisture-index': return 'NDMI';
            case 'moisture-stress': return 'NDMI';
            case 'ndwi': return 'NDWI';
            case 'agriculture': return 'AGRICULTURE';
            case 'barren-soil': return 'BARREN-SOIL';
            default: return 'TRUE-COLOR';
        }
    }, [metric]);

    useEffect(() => {
        if (!mapElement.current) return;

        // 1. BASE LAYER (ESRI World Imagery)
        const baseLayer = new TileLayer({
            source: new XYZ({
                url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                attributions: 'Tiles &copy; Esri',
            }),
        });

        // 2. SENTINEL WMS LAYER
        const layers: any[] = [baseLayer];
        
        if (provider === 'sentinel') {
            const isAnalytical = metric !== 'none';
            
            if (isAnalytical) {
                // Path-safe evalscript lookup with fallback
                const evalscript = EVALSCRIPTS[metric as keyof typeof EVALSCRIPTS] || EVALSCRIPTS['ndvi'] || EVALSCRIPTS['true-color'];
                
                if (!evalscript) {
                    console.error(`[SatelliteMap] No valid evalscript found for metric: ${metric}`);
                }
                
                const analyticalSource = new TileWMS({
                    url: '/api/satellite/sentinel/process', 
                    params: { 'LAYERS': 'sentinel-2-l2a', 'RANDOM': Math.random() }, // Cache busting
                    transition: 0,
                    projection: 'EPSG:3857' // Force immediate grid creation
                });

                analyticalSource.setTileLoadFunction(async (tile) => {
                    const imageTile = tile as any;
                    let grid = analyticalSource.getTileGrid();
                    
                    if (!grid) {
                        // Fallback: Create a standard XYZ tile grid if the source hasn't initialized one yet
                        const { createXYZ } = await import('ol/tilegrid');
                        grid = createXYZ();
                    }
                    
                    const tileCoord = imageTile.getTileCoord();
                    const extent = grid.getTileCoordExtent(tileCoord);
                    
                    // Transform BBOX from EPSG:3857 to EPSG:4326 for CDSE Process API
                    const p1 = olTransform([extent[0], extent[1]], 'EPSG:3857', 'EPSG:4326');
                    const p2 = olTransform([extent[2], extent[3]], 'EPSG:3857', 'EPSG:4326');
                    const bbox = [p1[0], p1[1], p2[0], p2[1]];
                    
                    // console.log(`[SatelliteMap] Loading tile ${tileCoord.join(',')} | BBOX: ${bbox.map(n => n.toFixed(4)).join(',')}`);

                    if (!date || date === 'none') {
                        console.error("[SatelliteMap] No date available for tile load");
                        return;
                    }

                    try {
                        const response = await fetch('/api/satellite/sentinel/process', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json', 'Accept': 'image/png' },
                            body: JSON.stringify({
                                input: {
                                    bounds: { bbox, properties: { crs: "http://www.opengis.net/def/crs/EPSG/0/4326" } },
                                    data: [{ type: "sentinel-2-l2a", timeRange: { from: `${date}T00:00:00Z`, to: `${date}T23:59:59Z` } }],
                                },
                                output: { width: 256, height: 256, responses: [{ identifier: "default", format: { type: "image/png" } }] },
                                evalscript: evalscript,
                            })
                        });

                        if (response.ok) {
                            const blob = await response.blob();
                            imageTile.getImage().src = URL.createObjectURL(blob);
                        } else {
                            const err = await response.text();
                            console.error(`[SatelliteMap] Tile load failed (${response.status}):`, err.slice(0, 100));
                        }
                    } catch (err) {
                        console.error("[SatelliteMap] Network error loading tile:", err);
                    }
                });

                layers.push(new TileLayer({
                    source: analyticalSource,
                    opacity: 0.9,
                    zIndex: 10
                }));
            } else {
                // PATH A: VISUAL (Standard CDSE WMS)
                const wmsLayer = new TileLayer({
                    source: new TileWMS({
                        url: '/api/satellite/sentinel/wms',
                        params: {
                            'LAYERS': 'S2L2A', // CDSE Standard True Color
                            'FORMAT': 'image/png',
                            'TRANSPARENT': true,
                            'VERSION': '1.3.0',
                            'CRS': 'EPSG:3857',
                            'TIME': date
                        },
                        transition: 0,
                    }),
                    opacity: 0.9
                });
                layers.push(wmsLayer);
            }
        }

        // 3. HEATMAP RASTER LAYER (SIMULATION)
        if (rasterPixels.length > 0 && provider !== 'sentinel') {
            const rasterSource = new VectorSource();
            rasterPixels.forEach(p => {
                // Convert bounds [[minLat, minLng], [maxLat, maxLng]] to OL coordinates
                const coords = [
                    [
                        fromLonLat([p.bounds[0][1], p.bounds[0][0]]),
                        fromLonLat([p.bounds[1][1], p.bounds[0][0]]),
                        fromLonLat([p.bounds[1][1], p.bounds[1][0]]),
                        fromLonLat([p.bounds[0][1], p.bounds[1][0]]),
                        fromLonLat([p.bounds[0][1], p.bounds[0][0]])
                    ]
                ];
                const feature = new Feature({
                    geometry: new Polygon(coords)
                });
                feature.setStyle(new Style({
                    fill: new Fill({ color: p.color + 'D9' }), // Added opacity D9 (85%)
                }));
                rasterSource.addFeature(feature);
            });
            
            layers.push(new VectorLayer({ source: rasterSource }));
        }

        // 4. FIELD BOUNDARY (GEOJSON)
        if (geoJson) {
            const vectorSource = new VectorSource({
                features: new GeoJSON().readFeatures(geoJson, {
                    dataProjection: 'EPSG:4326',
                    featureProjection: 'EPSG:3857',
                }),
            });

            const vectorLayer = new VectorLayer({
                source: vectorSource,
                style: new Style({
                    stroke: new Stroke({
                        color: '#ffffff',
                        width: 2,
                        lineDash: [4, 8]
                    }),
                    fill: new Fill({
                        color: 'rgba(255, 255, 255, 0.05)',
                    }),
                }),
            });
            layers.push(vectorLayer);
        }

        // INITIALIZE MAP
        const map = new Map({
            target: mapElement.current,
            layers: layers,
            view: new View({
                center: fromLonLat([lng, lat]),
                zoom: 16,
            }),
            controls: [],
        });

        if (geoJson) {
            const source = (layers[layers.length - 1] as unknown as VectorLayer<any>).getSource();
            if (source instanceof VectorSource) {
                const extent = source.getExtent();
                if (extent && extent[0] !== Infinity) {
                    map.getView().fit(extent, { padding: [50, 50, 50, 50], duration: 1000 });
                }
            }
        }

        mapRef.current = map;

        // Force resolution computation
        setTimeout(() => {
            if (mapRef.current) {
                mapRef.current.updateSize();
            }
        }, 0);

        return () => {
            map.setTarget(undefined);
            mapRef.current = null;
        };
    }, [lat, lng, geoJson, metric, provider, date, rasterPixels, wmsLayerId]);

    return (
        <div className="relative w-full h-full bg-slate-900 border-2 border-slate-800 rounded-lg overflow-hidden shadow-2xl">
            <div ref={mapElement} className="w-full h-full" />
            
            {/* Scale/Legend Overlay (Copernicus Style) */}
            <div className="absolute bottom-4 right-4 z-10 bg-slate-900/80 backdrop-blur-md p-2 rounded border border-slate-700 pointer-events-none flex items-center gap-2">
                <div className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Low</div>
                <div className="flex h-2 w-32 rounded-full overflow-hidden bg-gradient-to-r from-red-800 via-yellow-500 to-emerald-800 shadow-inner"></div>
                <div className="text-[10px] font-bold text-emerald-400 uppercase tracking-widest">High</div>
            </div>

            {/* Provider Attribution */}
            <div className="absolute top-4 right-4 z-10 bg-black/40 backdrop-blur-sm px-2 py-1 rounded text-[9px] text-white/60 font-medium">
                {provider === 'sentinel' ? 'Copernicus Sentinel-2' : 'Digital Twin Simulation'}
            </div>
        </div>
    );
}
