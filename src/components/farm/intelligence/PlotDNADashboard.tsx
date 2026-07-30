"use client";

import React, { useState, useEffect, useRef } from 'react';

const InfoTooltip = ({ text }: { text: string }) => (
  <div className="relative group inline-block ml-2 cursor-help z-50">
    <svg className="w-4 h-4 text-slate-500 hover:text-indigo-400 transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
    <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-3 bg-slate-800 text-slate-200 text-xs rounded-xl shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all pointer-events-none normal-case font-normal border border-slate-700">
      {text}
      <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-slate-800"></div>
    </div>
  </div>
);

// Interfaces for our new real-data payloads
interface PlotProps {
  plot?: {
    id: string;
    name?: string;
    geoJson?: any;
  };
}

export default function PlotDNADashboard({ plot }: PlotProps) {
  const [activeRegime, setActiveRegime] = useState<'optimal' | 'drought' | 'flood' | 'heatwave'>('optimal');
  const [isSequencing, setIsSequencing] = useState(false);
  const [hasStarted, setHasStarted] = useState(false);
  const [dnaData, setDnaData] = useState<any>(null);
  const [nerveLog, setNerveLog] = useState<string[]>([]);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const cameraRef = useRef({ x: 0, y: 0, zoom: 1, rotation: 0 });
  const isDraggingRef = useRef(false);
  const lastMousePosRef = useRef({ x: 0, y: 0 });
  const [usedFallbackCoords, setUsedFallbackCoords] = useState(false);

  // Add a line to the Autonomous Nerve Center
  const logToNerveCenter = (msg: string) => {
    setNerveLog(prev => [...prev, `[${new Date().toISOString().substring(11, 19)}] ${msg}`]);
  };

  // Fetch TRUE data from the backend
  const handleStartSequence = async () => {
    if (!plot) return;
    setHasStarted(true);
    setIsSequencing(true);

    try {
      // Extract coordinates from geoJson
      let lat = 36.75;
      let lng = 3.05;
      let polygon: [number, number][] | null = null;
      let isFallback = true;
      
      if (plot.geoJson?.geometry?.coordinates) {
        try {
          const coords = plot.geoJson.geometry.type === 'MultiPolygon' 
            ? plot.geoJson.geometry.coordinates[0][0] 
            : plot.geoJson.geometry.coordinates[0];
          
          if (coords && coords.length > 0) {
            polygon = coords;
            const lats = coords.map((c: any) => c[1]);
            const lngs = coords.map((c: any) => c[0]);
            lat = (Math.min(...lats) + Math.max(...lats)) / 2;
            lng = (Math.min(...lngs) + Math.max(...lngs)) / 2;
            isFallback = false;
          }
        } catch (e) {
          console.error("Failed to parse plot GeoJSON", e);
        }
      }

      setUsedFallbackCoords(isFallback);
      if (isFallback) {
        logToNerveCenter("⚠️ WARNING: No polygon geometry found. Using approximate default coordinates.");
      }

      logToNerveCenter("Initializing Generative Agronomic Inversion...");
      logToNerveCenter(`Target Plot: ${plot.id} | Center: ${lat.toFixed(4)}, ${lng.toFixed(4)}`);
      logToNerveCenter("Requesting Sentinel-2 raster composite and ERA5 climate archive...");
      
      const reqPayload = {
        plot_id: plot.id,
        lat: lat,
        lng: lng,
        polygon: polygon
      };

      const res = await fetch('/api/agribrain/plot-dna', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(reqPayload)
      });

      if (!res.ok) throw new Error("Failed to fetch DNA API");
      
      const data = await res.json();
      
      logToNerveCenter(`EO Data Fetched: ${data.fluid_topology.width}x${data.fluid_topology.height} native pixels.`);
      logToNerveCenter(`Multiverse: Computed ${data.multiverse.total_simulations} futures. Avg Yield: ${data.multiverse.average_yield.toFixed(1)}t/ha (σ=${data.multiverse.std_yield?.toFixed(1) || '?'})`);
      
      // Surface data quality warnings
      if (data.dna?.data_quality) {
        const dq = data.dna.data_quality;
        if (dq.weather_null_fill_pct > 0) {
          logToNerveCenter(`⚠️ Data Quality: ${dq.weather_null_fill_pct}% of weather days had missing values (null-filled).`);
        }
        logToNerveCenter(`Pipeline: ${dq.ndvi_observations} NDVI obs + ${dq.weather_records_total} weather records over ${dq.ndvi_observation_window_days}d window.`);
      }

      // Surface advanced phenometrics telemetry with quality awareness
      const ap = data.dna?.advanced_phenometrics;
      if (ap) {
        // P0: Pedogenic with fallback awareness
        const pmStatus = ap.pedogenic_memory?.status;
        if (pmStatus === 'ok' || pmStatus === 'partial' || pmStatus === 'fallback') {
          const pmBadge = pmStatus === 'fallback' ? '⚠️ FALLBACK' : pmStatus === 'partial' ? '⚠️ PARTIAL' : '✓';
          logToNerveCenter(`🪨 Pedogenic [${pmBadge}]: ${ap.pedogenic_memory.texture_class} | PAWC=${ap.pedogenic_memory.pawc_mm_per_m}mm/m | pH=${ap.pedogenic_memory.ph} (${ap.pedogenic_memory.ph_label})`);
          if (ap.pedogenic_memory.quality_note) {
            logToNerveCenter(`   ↳ ${ap.pedogenic_memory.quality_note}`);
          }
        }
        if (ap.phenological_fingerprint?.status === 'ok') {
          logToNerveCenter(`🌱 Phenology: ${ap.phenological_fingerprint.total_seasons} seasons detected | Stability: ${ap.phenological_fingerprint.stability_label} (CV=${ap.phenological_fingerprint.inter_annual_cv})`);
        }
        // P1: Hydro with null-fill awareness
        if (ap.hydrological_resilience?.status === 'ok') {
          const hrNf = ap.hydrological_resilience.null_filled_days_excluded;
          const hrExtra = hrNf > 0 ? ` | ${hrNf} null-filled days excluded` : '';
          logToNerveCenter(`💧 Hydro Resilience: ${ap.hydrological_resilience.resilience_label} | ${ap.hydrological_resilience.drought_events_detected} droughts | Tau=${ap.hydrological_resilience.recovery_tau_days ?? '∞'}d${hrExtra}`);
          if (ap.hydrological_resilience.quality_note) logToNerveCenter(`   ↳ ${ap.hydrological_resilience.quality_note}`);
        }
        // P1+P3: Stress with confidence awareness
        if (ap.stress_chronology?.status === 'ok') {
          logToNerveCenter(`🔥 Stress: ${ap.stress_chronology.total_stress_events} events (${ap.stress_chronology.compound_events} compound) | Worst: ${ap.stress_chronology.worst_month} | Thermal onset: ${ap.stress_chronology.thermal_onset_c ?? 32}°C`);
          if (ap.stress_chronology.quality_note) logToNerveCenter(`   ↳ ${ap.stress_chronology.quality_note}`);
        }
        if (ap.microclimate_divergence?.status === 'ok') {
          logToNerveCenter(`🌡️ Microclimate: ${ap.microclimate_divergence.advantage_label} | Model Confidence: ${ap.microclimate_divergence.model_confidence}`);
        }
        // P2: SPAC with proxy disclaimer
        if (ap.spac_efficiency?.status === 'ok') {
          const smTag = ap.spac_efficiency.sm_source === 'water_balance_proxy' ? ' [SM=Proxy]' : '';
          logToNerveCenter(`🌿 SPAC: TE=${ap.spac_efficiency.te_label} | Decoupling: ${ap.spac_efficiency.decoupling_label}${smTag}`);
        }
        logToNerveCenter(`✅ Advanced Phenometrics suite complete (6 modules).`);
      }
      
      setDnaData(data);
    } catch (err: any) {
      logToNerveCenter(`CRITICAL ERROR: ${err.message}`);
      logToNerveCenter("Check backend logs. Sentinel-2 processing may have failed or rate limited.");
    } finally {
      setTimeout(() => setIsSequencing(false), 2000);
    }
  };

  // 3D Canvas Renderer for the Fluid Topology
  useEffect(() => {
    if (!canvasRef.current || !dnaData || isSequencing) return;
    
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    
    const grid = dnaData.fluid_topology.regimes[activeRegime];
    if (!grid || grid.length === 0) return;
    
    const rows = grid.length;
    const cols = grid[0].length;
    
    // Parse hex to get a pseudo-elevation (brighter/greener = higher)
    const getZ = (hex: string, cellH: number) => {
      if (hex === 'transparent') return 0;
      const r = parseInt(hex.slice(1,3), 16);
      const g = parseInt(hex.slice(3,5), 16);
      // Ensure positive extrusion, scaled to cell size
      const elevation = Math.max(0, g - r); 
      return elevation * (cellH / 30); 
    };

    // Collect all cells
    const cells: {x: number, y: number, hex: string}[] = [];
    for (let y = 0; y < rows; y++) {
      for (let x = 0; x < cols; x++) {
        const hex = grid[y][x];
        if (hex !== 'transparent') {
          cells.push({ x, y, hex });
        }
      }
    }

    let animationFrameId: number;

    const render = () => {
      const w = canvas.width;
      const h = canvas.height;
      ctx.clearRect(0, 0, w, h);
      
      const { x: panX, y: panY, zoom, rotation } = cameraRef.current;
      
      // Dynamically scale the cells to fit the canvas
      const maxGridDim = Math.max(rows, cols);
      const cellW = Math.max(2, Math.floor(w / (maxGridDim * 2.2))) * zoom;
      const cellH = cellW; // Keep isometric aspect ratio
      
      // Center the grid in the canvas + Pan offsets
      const originX = w / 2 + panX;
      const originY = h / 2 - (maxGridDim * cellH) / 4 + panY;
      
      // Base extrusion depth based on cell size
      const depth = Math.max(4, cellH * 1.5);

      // Center of rotation
      const centerX = cols / 2;
      const centerY = rows / 2;
      const cosT = Math.cos(rotation);
      const sinT = Math.sin(rotation);

      // Compute rotated coordinates and dynamic depth
      const projectedCells = cells.map(cell => {
        const cx = cell.x - centerX;
        const cy = cell.y - centerY;
        const rx = cx * cosT - cy * sinT;
        const ry = cx * sinT + cy * cosT;
        return { ...cell, rx, ry, depthScore: rx + ry };
      });

      // Sort from back to front dynamically based on rotation
      projectedCells.sort((a, b) => a.depthScore - b.depthScore);

      // Draw from back to front
      for (const cell of projectedCells) {
        const { rx, ry, hex } = cell;
        const z = getZ(hex, cellH);
        
        // Iso math
        const screenX = originX + (rx - ry) * cellW;
        const screenY = originY + (rx + ry) * (cellH / 2) - z;
        
        // Draw pillar top face
        ctx.fillStyle = hex;
        ctx.beginPath();
        ctx.moveTo(screenX, screenY);
        ctx.lineTo(screenX + cellW, screenY + cellH/2);
        ctx.lineTo(screenX, screenY + cellH);
        ctx.lineTo(screenX - cellW, screenY + cellH/2);
        ctx.closePath();
        ctx.fill();
        ctx.strokeStyle = 'rgba(0,0,0,0.1)';
        ctx.stroke();
        
        // Left face
        ctx.fillStyle = darken(hex, 0.7);
        ctx.beginPath();
        ctx.moveTo(screenX - cellW, screenY + cellH/2);
        ctx.lineTo(screenX, screenY + cellH);
        ctx.lineTo(screenX, screenY + cellH + depth + z);
        ctx.lineTo(screenX - cellW, screenY + cellH/2 + depth + z);
        ctx.closePath();
        ctx.fill();
        
        // Right face
        ctx.fillStyle = darken(hex, 0.5);
        ctx.beginPath();
        ctx.moveTo(screenX, screenY + cellH);
        ctx.lineTo(screenX + cellW, screenY + cellH/2);
        ctx.lineTo(screenX + cellW, screenY + cellH/2 + depth + z);
        ctx.lineTo(screenX, screenY + cellH + depth + z);
        ctx.closePath();
        ctx.fill();
      }
    };

    // Interaction Event Handlers
    const handleMouseDown = (e: MouseEvent) => {
      isDraggingRef.current = true;
      lastMousePosRef.current = { x: e.clientX, y: e.clientY };
      canvas.style.cursor = 'grabbing';
    };

    const handleMouseMove = (e: MouseEvent) => {
      if (!isDraggingRef.current) return;
      const dx = e.clientX - lastMousePosRef.current.x;
      const dy = e.clientY - lastMousePosRef.current.y;
      
      if (e.buttons === 2 || e.shiftKey) {
        // Right click or Shift+Left -> Rotate around Z axis
        cameraRef.current.rotation += dx * 0.01;
      } else {
        // Left click -> Pan
        cameraRef.current.x += dx;
        cameraRef.current.y += dy;
      }
      
      lastMousePosRef.current = { x: e.clientX, y: e.clientY };
      
      animationFrameId = requestAnimationFrame(render);
    };

    const handleMouseUp = () => {
      isDraggingRef.current = false;
      canvas.style.cursor = 'grab';
    };

    const handleWheel = (e: WheelEvent) => {
      e.preventDefault();
      const zoomSpeed = 0.002;
      let newZoom = cameraRef.current.zoom - e.deltaY * zoomSpeed;
      newZoom = Math.max(0.2, Math.min(10, newZoom));
      cameraRef.current.zoom = newZoom;
      
      animationFrameId = requestAnimationFrame(render);
    };

    const handleContextMenu = (e: MouseEvent) => e.preventDefault();

    // Attach listeners
    canvas.style.cursor = 'grab';
    canvas.addEventListener('mousedown', handleMouseDown);
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    canvas.addEventListener('wheel', handleWheel, { passive: false });
    canvas.addEventListener('contextmenu', handleContextMenu);
    
    // Initial render
    render();

    return () => {
      cancelAnimationFrame(animationFrameId);
      canvas.removeEventListener('mousedown', handleMouseDown);
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
      canvas.removeEventListener('wheel', handleWheel);
      canvas.removeEventListener('contextmenu', handleContextMenu);
    };
  }, [dnaData, activeRegime, isSequencing]);

  // Helper for 3D pillar shading
  const darken = (hex: string, factor: number) => {
    let r = parseInt(hex.slice(1,3), 16) * factor;
    let g = parseInt(hex.slice(3,5), 16) * factor;
    let b = parseInt(hex.slice(5,7), 16) * factor;
    return `rgb(${Math.floor(r)},${Math.floor(g)},${Math.floor(b)})`;
  };

  if (!plot) {
    return <div className="text-white">Please select a plot to sequence DNA.</div>;
  }

  if (!hasStarted) {
    return (
      <div className="mt-12 space-y-6">
        <div className="p-8 rounded-3xl bg-slate-900 border border-slate-800 flex flex-col items-center justify-center min-h-[400px]">
          <h3 className="text-2xl font-bold text-white mb-4">Plot DNA 3.0: Quantum Agronomy</h3>
          <p className="text-slate-400 text-center max-w-lg mb-8">
            Perform a highly intensive biophysical inversion using real 10-year Earth Observation telemetry to generate a holographic spatial twin and 2030 multiverse yield projection.
          </p>
          <button 
            onClick={handleStartSequence}
            className="bg-gradient-to-r from-fuchsia-600 to-indigo-600 hover:from-fuchsia-500 hover:to-indigo-500 text-white font-bold py-3 px-8 rounded-xl shadow-lg shadow-fuchsia-500/30 transition-all hover:scale-105 active:scale-95 flex items-center gap-3"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path></svg>
            Sequence Decadal Plot DNA
          </button>
        </div>
      </div>
    );
  }

  if (isSequencing || !dnaData) {
    return (
      <div className="mt-12 space-y-6">
        <div className="p-8 rounded-3xl bg-slate-900 border border-slate-800 flex flex-col items-center justify-center min-h-[400px]">
          <div className="w-16 h-16 relative flex items-center justify-center mb-6">
            <div className="absolute inset-0 rounded-full border-t-2 border-indigo-500 animate-spin"></div>
            <div className="absolute inset-2 rounded-full border-b-2 border-fuchsia-500 animate-spin" style={{ animationDirection: 'reverse' }}></div>
          </div>
          <h3 className="text-xl font-bold text-white bg-clip-text text-transparent bg-gradient-to-r from-indigo-400 to-fuchsia-400">
            Sequencing Plot DNA from Real Satellite Telemetry
          </h3>
          <div className="mt-6 w-full max-w-2xl bg-black rounded-lg p-4 font-mono text-xs text-emerald-400 h-48 overflow-y-auto border border-slate-800">
            {nerveLog.map((log, i) => (
              <div key={i}>{log}</div>
            ))}
            <div className="animate-pulse">_</div>
          </div>
        </div>
      </div>
    );
  }

  const { dna, multiverse, terraforming } = dnaData;

  return (
    <div className="mt-12 space-y-6">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h2 className="text-3xl font-black text-white flex items-center gap-3">
            <span className="bg-gradient-to-br from-fuchsia-600 to-indigo-600 rounded-xl p-2 shadow-lg shadow-fuchsia-500/20 text-white">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path></svg>
            </span>
            Plot DNA 3.0: Quantum Agronomy
          </h2>
          <p className="text-slate-400 mt-2 text-sm">Real-Data Digital Twin & Multiverse Predictive Engine</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left Col: 3D Digital Twin */}
        <div className="lg:col-span-2 bg-slate-900 border border-slate-800 rounded-3xl p-0 overflow-hidden flex flex-col relative">
          <div className="p-6 border-b border-slate-800 flex justify-between items-center bg-slate-900/80 backdrop-blur-md z-10">
            <div>
              <h3 className="text-white font-bold flex items-center gap-2">
                <svg className="text-indigo-500" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="3 6 9 3 15 6 21 3 21 18 15 21 9 18 3 21"></polygon></svg>
                3D Holographic Digital Twin
                <InfoTooltip text="Height & Greenness represent historic biomass vigor (productivity). Red/Yellow depressions highlight chronic structural weaknesses (e.g., poor drainage). Toggling climate regimes reveals physical vulnerabilities." />
              </h3>
              <p className="text-xs text-slate-400 mt-1">Isometric WebGL rendering of native Sentinel-2 raster variance.</p>
            </div>
            
            <div className="flex bg-slate-800 p-1 rounded-xl">
              {['optimal', 'drought', 'flood', 'heatwave'].map(regime => (
                <button 
                  key={regime}
                  onClick={() => setActiveRegime(regime as any)}
                  className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-all ${activeRegime === regime ? 'bg-indigo-500 text-white shadow-md' : 'text-slate-400 hover:text-white'}`}
                >
                  {regime.charAt(0).toUpperCase() + regime.slice(1)}
                </button>
              ))}
            </div>
          </div>
          
          <div className="flex-1 relative bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-slate-800 via-slate-950 to-black flex items-center justify-center p-0 min-h-[400px]">
             {/* Actual 3D Canvas */}
             <canvas ref={canvasRef} width={800} height={500} className="w-full h-full object-contain mix-blend-screen opacity-90"></canvas>
             
             {/* Holographic Overlay Effects */}
             <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyMCIgaGVpZ2h0PSIyMCI+PHBhdGggZD0iTTAgMGgyMHYyMEgwem0xMCAxMGgxMHYxMEgxMHoiIGZpbGw9IiNmZmYiIGZpbGwtb3BhY2l0eT0iLjAyNSIvPjwvc3ZnPg==')] opacity-30 pointer-events-none"></div>
          </div>
        </div>

        {/* Right Col: Agronomic Genome & Autonomous Nerve Center */}
        <div className="space-y-6 flex flex-col">
          <div className="bg-slate-900/50 backdrop-blur-xl border border-slate-800 rounded-3xl p-6 relative overflow-hidden group flex-shrink-0">
            <h3 className="text-white font-bold mb-6 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-fuchsia-500 shadow-[0_0_10px_rgba(217,70,239,0.8)]"></span>
              The Agronomic Genome
            </h3>
            
            <div className="space-y-5">
              <TraitBar label="Biomass Vigor (α)" value={dna.traits.alpha_vigor} max={1.5} color="bg-emerald-500" tooltipText="The maximum growth engine of the field under perfect weather." />
              <TraitBar label="Water Retention (θ)" value={dna.traits.theta_retention} max={1.5} color="bg-amber-500" tooltipText="The field's sponge capacity. Low scores indicate fast drainage and high vulnerability to dry spells." />
              <TraitBar label="Thermal Penalty (β)" value={dna.traits.beta_resilience} max={5.0} color="bg-rose-500" tooltipText="How severely the crop shuts down photosynthesis during extreme heatwaves." />
            </div>
          </div>

          <div className="bg-black border border-slate-800 rounded-3xl p-4 flex-1 flex flex-col font-mono relative overflow-hidden shadow-inner">
            <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-emerald-500 to-indigo-500"></div>
            <h3 className="text-emerald-500 font-bold mb-3 text-xs tracking-widest flex justify-between">
              <span>SYSTEM.NERVE_CENTER</span>
              <span className="animate-pulse">LIVE_FEED</span>
            </h3>
            <div className="flex-1 overflow-y-auto text-[10px] text-emerald-400/80 space-y-1">
              {nerveLog.map((log, i) => (
                <div key={i} className="hover:text-emerald-300 hover:bg-emerald-900/20 px-1 rounded">{log}</div>
              ))}
              <div>_</div>
            </div>
          </div>
        </div>

      </div>

      {/* Bottom Row: Multiverse & Terraforming */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        
        {/* Multiverse Scatter */}
        <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6">
          <h3 className="text-white font-bold mb-2 flex items-center gap-2">
            <svg className="text-fuchsia-500" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path><polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline><line x1="12" y1="22.08" x2="12" y2="12"></line></svg>
            Multiverse Yield Projection (2030)
            <InfoTooltip text="Tests the plot's genome against 2,000 future climate scenarios. A wide scatter of red dots falling to the bottom-right indicates severe fragility and high Catastrophe Risk." />
          </h3>
          <p className="text-xs text-slate-400 mb-6 max-w-lg">
            Monte Carlo engine ran {multiverse.total_simulations} stochastic climate variations against the plot's true DNA.
          </p>
          
          <div className="grid grid-cols-3 gap-4 mb-6">
            <div className="bg-slate-950 rounded-xl p-3 border border-slate-800">
              <span className="text-[10px] uppercase text-slate-500 font-bold block mb-1">Average Yield</span>
              <span className="text-2xl font-black text-white">{multiverse.average_yield.toFixed(1)}t</span>
            </div>
            <div className="bg-emerald-950/30 rounded-xl p-3 border border-emerald-900/50">
              <span className="text-[10px] uppercase text-emerald-500 font-bold block mb-1">Record Prob.</span>
              <span className="text-2xl font-black text-emerald-400">{(multiverse.record_probability * 100).toFixed(1)}%</span>
            </div>
            <div className="bg-rose-950/30 rounded-xl p-3 border border-rose-900/50">
              <span className="text-[10px] uppercase text-rose-500 font-bold block mb-1">Catastrophe Risk</span>
              <span className="text-2xl font-black text-rose-400">{(multiverse.catastrophe_probability * 100).toFixed(1)}%</span>
            </div>
          </div>

          {/* Simple Scatter Plot Viz */}
          <div className="relative w-full h-48 bg-slate-950 rounded-xl border border-slate-800 overflow-hidden flex items-end p-2">
             <div className="absolute inset-0 grid grid-cols-4 grid-rows-4 opacity-10">
               {Array.from({length: 16}).map((_,i) => <div key={i} className="border-t border-l border-white"></div>)}
             </div>
             {multiverse.scatter_points.map((pt: any) => {
               // Map yield (20-140) to height %, anomaly (-3 to 3) to width %
               const left = Math.max(0, Math.min(100, ((pt.temp_anomaly + 3) / 6) * 100));
               const bottom = Math.max(0, Math.min(100, (pt.projected_yield / 140) * 100));
               const color = pt.projected_yield > 100 ? 'bg-emerald-400' : pt.projected_yield < 40 ? 'bg-rose-500' : 'bg-indigo-400';
               return (
                 <div key={pt.id} 
                      className={`absolute w-1.5 h-1.5 rounded-full ${color} opacity-60 shadow-[0_0_5px_currentColor] transition-all hover:scale-150 hover:z-10`}
                      style={{ left: `${left}%`, bottom: `${bottom}%` }}
                      title={`Yield: ${pt.projected_yield}t | Temp Shift: ${pt.temp_anomaly}°C`}
                 />
               );
             })}
             <div className="absolute bottom-1 left-2 text-[10px] text-slate-500 font-mono">-3°C Temp Anomaly</div>
             <div className="absolute bottom-1 right-2 text-[10px] text-slate-500 font-mono">+3°C Temp Anomaly</div>
          </div>
        </div>

        {/* Terraforming ROI */}
         <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6">
           <h3 className="text-white font-bold mb-2 flex items-center gap-2">
            <svg className="text-amber-500" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>
            Terraforming ROI Simulator
            <InfoTooltip text="Simulates physically 'mutating' the field's genome (e.g., fixing red depressions with drainage) and calculates the 10-year financial ROI of the resulting yield resilience." />
          </h3>
          <p className="text-xs text-slate-400 mb-6">
            Physical soil interventions directly mutate the DNA profile, rerunning the Multiverse to calculate precise 10-year financial ROI.
          </p>

          <div className="space-y-4">
            {Object.keys(terraforming).map(key => {
              const data = terraforming[key];
              return (
                <div key={key} className="bg-slate-950 border border-slate-800 rounded-2xl p-4 flex items-center justify-between group hover:border-slate-600 transition-colors cursor-pointer relative overflow-hidden">
                  <div className={`absolute left-0 top-0 bottom-0 w-1 ${data.roi_10yr_pct > 0 ? 'bg-emerald-500' : 'bg-rose-500'}`}></div>
                  <div className="pl-3">
                    <h4 className="text-sm font-bold text-white">{data.intervention}</h4>
                    <div className="flex gap-4 mt-1 text-[10px] text-slate-400">
                      <span>CAPEX: ${data.cost_per_ha}/ha</span>
                      <span>Yield Delta: +{data.yield_increase_tons}t</span>
                    </div>
                  </div>
                  <div className="text-right">
                    <span className={`text-xl font-black ${data.roi_10yr_pct > 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {data.roi_10yr_pct > 0 ? '+' : ''}{data.roi_10yr_pct}% ROI
                    </span>
                    <span className="block text-[9px] uppercase tracking-widest text-slate-500">10-Year Horizon</span>
                  </div>
                </div>
              );
            })}
          </div>
          <p className="text-[9px] text-slate-600 mt-4 italic">Costs and crop prices are illustrative estimates, not live market data.</p>
        </div>

      </div>

      {/* ================================================================ */}
      {/* Plot DNA 4.0: Advanced Phenometrics Visualizations              */}
      {/* ================================================================ */}
      {dnaData.dna?.advanced_phenometrics && (
        <>
          <div className="flex items-center gap-3 mt-4 mb-2">
            <div className="h-px flex-1 bg-gradient-to-r from-transparent via-fuchsia-500/30 to-transparent"></div>
            <span className="text-xs font-bold uppercase tracking-[0.2em] text-fuchsia-400/60">Advanced Phenometrics</span>
            <div className="h-px flex-1 bg-gradient-to-r from-transparent via-fuchsia-500/30 to-transparent"></div>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">

            {/* Card 1: Phenological Fingerprint */}
            {(() => {
              const pf = dnaData.dna.advanced_phenometrics.phenological_fingerprint;
              if (!pf || pf.status !== 'ok') return null;
              return (
                <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6">
                  <h3 className="text-white font-bold mb-1 flex items-center gap-2">
                    <span className="text-emerald-400">🌱</span>
                    Phenological Fingerprint
                    <InfoTooltip text="Decomposes multi-year NDVI into individual growing seasons. Green-up velocity measures canopy establishment speed; inter-annual CV reveals field stability." />
                  </h3>
                  <p className="text-[10px] text-slate-500 mb-4">{pf.total_seasons} seasons detected over observation window</p>
                  <div className="grid grid-cols-3 gap-3 mb-4">
                    <div className="bg-slate-950 rounded-xl p-2.5 border border-slate-800">
                      <span className="text-[9px] uppercase text-slate-500 font-bold block">Stability</span>
                      <span className={`text-lg font-black ${pf.stability_label === 'Stable' ? 'text-emerald-400' : pf.stability_label === 'Moderate' ? 'text-amber-400' : 'text-rose-400'}`}>{pf.stability_label}</span>
                    </div>
                    <div className="bg-slate-950 rounded-xl p-2.5 border border-slate-800">
                      <span className="text-[9px] uppercase text-slate-500 font-bold block">Peak Trend</span>
                      <span className={`text-lg font-black ${pf.peak_trend_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>{pf.peak_trend_pct > 0 ? '+' : ''}{pf.peak_trend_pct}%</span>
                    </div>
                    <div className="bg-slate-950 rounded-xl p-2.5 border border-slate-800">
                      <span className="text-[9px] uppercase text-slate-500 font-bold block">Avg Season</span>
                      <span className="text-lg font-black text-white">{pf.mean_season_length_days}d</span>
                    </div>
                  </div>
                  <div className="space-y-1.5">
                    {pf.seasons.slice(-5).map((s: any, i: number) => {
                      const peakPct = Math.min(100, (s.peak_ndvi / 0.9) * 100);
                      return (
                        <div key={i} className="flex items-center gap-2">
                          <span className="text-[10px] text-slate-500 w-10 font-mono">{s.year}</span>
                          <div className="flex-1 h-3 bg-slate-800 rounded-full overflow-hidden">
                            <div className="h-full rounded-full bg-gradient-to-r from-emerald-600 to-emerald-400 transition-all duration-700" style={{ width: `${peakPct}%` }} />
                          </div>
                          <span className="text-[10px] text-slate-400 w-12 text-right font-mono">{s.peak_ndvi.toFixed(2)}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })()}

            {/* Card 2: Soil-Water Intelligence */}
            {(() => {
              const pm = dnaData.dna.advanced_phenometrics.pedogenic_memory;
              const hr = dnaData.dna.advanced_phenometrics.hydrological_resilience;
              const sp = dnaData.dna.advanced_phenometrics.spac_efficiency;
              const pmUsable = pm?.status === 'ok' || pm?.status === 'partial' || pm?.status === 'fallback';
              return (
                <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6">
                  <h3 className="text-white font-bold mb-1 flex items-center gap-2">
                    <span className="text-cyan-400">💧</span>
                    Soil-Water Intelligence
                    <InfoTooltip text="Combines pedogenic soil analysis (USDA texture, Saxton-Rawls PAWC), hydrological drought resilience, and SPAC transpiration efficiency." />
                  </h3>
                  <p className="text-[10px] text-slate-500 mb-4">Pedogenic + Hydrological + SPAC fusion</p>

                  {/* P0: Pedogenic data quality banner */}
                  {pm?.status === 'fallback' && (
                    <div className="mb-3 px-3 py-1.5 rounded-lg bg-amber-950/40 border border-amber-700/40 flex items-center gap-2">
                      <span className="text-amber-400 text-[10px]">⚠</span>
                      <span className="text-[10px] text-amber-400/80">Soil data is a generic ISRIC estimate — no mapped pixel found for this location.</span>
                    </div>
                  )}
                  {pm?.status === 'partial' && (
                    <div className="mb-3 px-3 py-1.5 rounded-lg bg-yellow-950/30 border border-yellow-700/30 flex items-center gap-2">
                      <span className="text-yellow-400 text-[10px]">⚠</span>
                      <span className="text-[10px] text-yellow-400/70">Some soil properties used regional defaults: {pm.defaulted_fields?.join(', ')}</span>
                    </div>
                  )}

                  <div className="grid grid-cols-2 gap-3">
                    {pmUsable && (<>
                      <MetricTile label="Soil Texture" value={pm.texture_class} sub={`Clay ${pm.clay_pct}% · Sand ${pm.sand_pct}%`} badge={pm.is_generic_fallback ? 'EST' : undefined} />
                      <MetricTile label="PAWC" value={`${pm.pawc_mm_per_m}`} unit="mm/m" sub={`pH ${pm.ph} (${pm.ph_label})`} />
                      <MetricTile label="Bio Activity" value={pm.biological_activity?.label || '—'} sub={pm.biological_activity?.cn_ratio ? `C:N = ${pm.biological_activity.cn_ratio}` : ''} />
                      <MetricTile label="CEC" value={pm.cec_adequacy?.adequacy || '—'} sub={`${pm.cec_cmol_kg} cmol/kg`} />
                    </>)}
                    {hr?.status === 'ok' && (<>
                      <MetricTile label="Recovery τ" value={hr.recovery_tau_days ? `${hr.recovery_tau_days}d` : '—'} sub={hr.resilience_label} accent={hr.resilience_label === 'Highly Resilient' ? 'emerald' : hr.resilience_label === 'Fragile' ? 'rose' : 'amber'} />
                      <MetricTile label="PUE" value={`${hr.pue_ndvi_per_mm}`} unit="×10⁻³" sub={`${hr.drought_events_detected} droughts`} />
                    </>)}
                    {sp?.status === 'ok' && (<>
                      <MetricTile label="Transp. Eff." value={`${sp.transpiration_efficiency}`} sub={sp.te_label} accent={sp.te_label === 'Excellent' ? 'emerald' : sp.te_label === 'Low' ? 'rose' : 'amber'} />
                      <MetricTile label="Decoupling" value={sp.decoupling_label.split(' ')[0]} sub={sp.decoupling_detail} />
                    </>)}
                  </div>

                  {/* P2: SPAC SM proxy disclaimer */}
                  {sp?.sm_source === 'water_balance_proxy' && sp?.critical_sm_pct != null && (
                    <div className="mt-3 px-3 py-1.5 rounded-lg bg-slate-800/50 border border-slate-700/50 flex items-center gap-2">
                      <span className="text-slate-400 text-[10px]">ℹ</span>
                      <span className="text-[10px] text-slate-500">SM Threshold ({sp.critical_sm_pct}%) derived from water-balance model, not real soil sensors.</span>
                    </div>
                  )}
                </div>
              );
            })()}

            {/* Card 3: Stress Chronology Heatmap */}
            {(() => {
              const sc = dnaData.dna.advanced_phenometrics.stress_chronology;
              const mc = dnaData.dna.advanced_phenometrics.microclimate_divergence;
              if (!sc || sc.status !== 'ok') return null;
              return (
                <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6">
                  <h3 className="text-white font-bold mb-1 flex items-center gap-2">
                    <span className="text-rose-400">🔥</span>
                    Stress Chronology
                    <InfoTooltip text="Monthly heatmap of historical vegetation stress from the ProcessModel simulation. Compound events (heat + drought) are disproportionately damaging." />
                  </h3>
                  <p className="text-[10px] text-slate-500 mb-3">{sc.total_stress_events} events ({sc.compound_events} compound) | Worst: {sc.worst_month}</p>
                  {/* P1: Stress confidence warning */}
                  {sc.quality_note && (
                    <div className="mb-3 px-3 py-1.5 rounded-lg bg-amber-950/30 border border-amber-700/30">
                      <span className="text-[10px] text-amber-400/70">⚠ {sc.quality_note}</span>
                    </div>
                  )}
                  <div className="grid grid-cols-6 gap-1.5 mb-4">
                    {sc.monthly_calendar?.map((m: any) => {
                      const bg = m.stress_frequency > 0.4 ? 'bg-rose-500/80' : m.stress_frequency > 0.25 ? 'bg-orange-500/60' : m.stress_frequency > 0.1 ? 'bg-amber-500/40' : 'bg-slate-800';
                      return (
                        <div key={m.month} className={`${bg} rounded-lg p-2 text-center transition-all hover:scale-105 cursor-default`} title={`${m.month_name}: ${m.risk_level} risk`}>
                          <span className="text-[10px] font-bold text-white/80 block">{m.month_name}</span>
                          <span className="text-[9px] text-white/50 block">{(m.stress_frequency * 100).toFixed(0)}%</span>
                        </div>
                      );
                    })}
                  </div>
                  {mc?.status === 'ok' && (
                    <div className={`mt-3 p-3 rounded-xl border ${
                      mc.advantage_label === 'Microclimate Advantage' ? 'border-emerald-800 bg-emerald-950/30' :
                      mc.advantage_label === 'Microclimate Disadvantage' ? 'border-rose-800 bg-rose-950/30' :
                      'border-slate-700 bg-slate-800/30'
                    }`}>
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-white">🌡️ {mc.advantage_label}</span>
                        <span className="text-[10px] text-slate-400">Confidence: {mc.model_confidence}</span>
                      </div>
                      <p className="text-[10px] text-slate-400 mt-1">{mc.advantage_detail}</p>
                    </div>
                  )}
                </div>
              );
            })()}

          </div>
        </>
      )}

    </div>
  );
}

// MetricTile helper for Soil-Water Intelligence grid
function MetricTile({ label, value, unit, sub, accent, badge }: { label: string, value: string, unit?: string, sub?: string, accent?: string, badge?: string }) {
  const accentColor = accent === 'emerald' ? 'text-emerald-400' : accent === 'rose' ? 'text-rose-400' : accent === 'amber' ? 'text-amber-400' : 'text-white';
  return (
    <div className="bg-slate-950 rounded-xl p-2.5 border border-slate-800">
      <div className="flex items-center justify-between mb-0.5">
        <span className="text-[9px] uppercase text-slate-500 font-bold">{label}</span>
        {badge && <span className="text-[8px] px-1 py-0.5 rounded bg-amber-500/20 text-amber-400 font-bold">{badge}</span>}
      </div>
      <span className={`text-sm font-black ${accentColor}`}>{value}{unit && <span className="text-[10px] text-slate-500 ml-0.5">{unit}</span>}</span>
      {sub && <span className="text-[9px] text-slate-500 block mt-0.5 truncate">{sub}</span>}
    </div>
  );
}
function TraitBar({ label, value, max, color, tooltipText }: { label: string, value: number, max: number, color: string, tooltipText?: string }) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100));
  return (
    <div className="space-y-1.5">
      <div className="flex justify-between items-end">
        <span className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center">
          {label}
          {tooltipText && <InfoTooltip text={tooltipText} />}
        </span>
        <span className="text-xs font-mono text-slate-500">{value.toFixed(2)} / {max.toFixed(1)}</span>
      </div>
      <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full transition-all duration-1000 shadow-[0_0_10px_currentColor]`} style={{ width: `${pct}%` }}></div>
      </div>
    </div>
  );
}
