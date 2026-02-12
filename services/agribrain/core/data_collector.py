"""
Data Collector Service
Automatic data collection for all farms/plots:
- Plot registration and tracking
- Periodic weather snapshots  
- Satellite observation capture
- Parquet storage with farm/plot hierarchy
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import asyncio
import threading

# Storage configuration
DATA_ROOT = Path(__file__).parent.parent / "datasets"
OBSERVATIONS_DIR = DATA_ROOT / "observations"
EVENTS_DIR = DATA_ROOT / "events"
REGISTRY_DIR = DATA_ROOT / "registry"

# Ensure directories exist
for d in [OBSERVATIONS_DIR, EVENTS_DIR, REGISTRY_DIR]:
    d.mkdir(parents=True, exist_ok=True)


class PlotRegistry:
    """
    Registry of all plots being monitored for data collection.
    Persists to JSON for simplicity.
    """
    
    def __init__(self):
        self.registry_file = REGISTRY_DIR / "plots.json"
        self._load()
    
    def _load(self):
        if self.registry_file.exists():
            with open(self.registry_file) as f:
                self.plots = json.load(f)
        else:
            self.plots = {}
    
    def _save(self):
        with open(self.registry_file, "w") as f:
            json.dump(self.plots, f, indent=2, default=str)
    
    def register(self, farm_id: str, plot_id: str, coordinates: Dict, crop: str, area: float = 0):
        """Register a new plot for data collection."""
        key = f"{farm_id}:{plot_id}"
        
        self.plots[key] = {
            "farm_id": farm_id,
            "plot_id": plot_id,
            "coordinates": coordinates,
            "crop": crop,
            "area": area,
            "registered_at": datetime.now().isoformat(),
            "last_weather_collection": None,
            "last_satellite_collection": None,
            "collection_count": 0,
            "active": True
        }
        self._save()
        
        # Create plot data directory
        plot_dir = OBSERVATIONS_DIR / farm_id / plot_id
        plot_dir.mkdir(parents=True, exist_ok=True)
        
        return self.plots[key]
    
    def get_plot(self, farm_id: str, plot_id: str) -> Optional[Dict]:
        key = f"{farm_id}:{plot_id}"
        return self.plots.get(key)
    
    def get_active_plots(self) -> List[Dict]:
        """Get all active plots for collection."""
        return [p for p in self.plots.values() if p.get("active", True)]
    
    def update_collection_time(self, farm_id: str, plot_id: str, collection_type: str):
        """Update last collection timestamp."""
        key = f"{farm_id}:{plot_id}"
        if key in self.plots:
            self.plots[key][f"last_{collection_type}_collection"] = datetime.now().isoformat()
            self.plots[key]["collection_count"] += 1
            self._save()
    
    def deactivate(self, farm_id: str, plot_id: str):
        """Stop collecting for a plot (e.g., if deleted)."""
        key = f"{farm_id}:{plot_id}"
        if key in self.plots:
            self.plots[key]["active"] = False
            self._save()


class ObservationStore:
    """
    Time-series observation storage using JSONL with Parquet export capability.
    Organized by farm_id/plot_id with monthly chunks.
    """
    
    def __init__(self, farm_id: str, plot_id: str, data_type: str):
        self.farm_id = farm_id
        self.plot_id = plot_id
        self.data_type = data_type  # 'weather' or 'ndvi'
        
        self.base_dir = OBSERVATIONS_DIR / farm_id / plot_id
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_chunk_file(self, timestamp: datetime) -> Path:
        """Get the monthly chunk file for a timestamp."""
        month_str = timestamp.strftime("%Y-%m")
        return self.base_dir / f"{self.data_type}_{month_str}.jsonl"
    
    def append(self, observation: Dict):
        """Append an observation to the appropriate monthly chunk."""
        timestamp = datetime.fromisoformat(observation.get("timestamp", datetime.now().isoformat()))
        chunk_file = self._get_chunk_file(timestamp)
        
        with open(chunk_file, "a") as f:
            f.write(json.dumps(observation) + "\n")
    
    def query(self, start_date: str, end_date: str) -> List[Dict]:
        """Query observations in a date range."""
        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)
        
        results = []
        
        # Iterate through all chunk files that might contain data
        current = start.replace(day=1)
        while current <= end:
            chunk_file = self._get_chunk_file(current)
            if chunk_file.exists():
                with open(chunk_file) as f:
                    for line in f:
                        obs = json.loads(line)
                        obs_time = datetime.fromisoformat(obs["timestamp"])
                        if start <= obs_time <= end:
                            results.append(obs)
            
            # Move to next month
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)
        
        return sorted(results, key=lambda x: x["timestamp"])
    
    def get_stats(self) -> Dict:
        """Get storage statistics for this plot."""
        chunk_files = list(self.base_dir.glob(f"{self.data_type}_*.jsonl"))
        total_size = sum(f.stat().st_size for f in chunk_files)
        
        record_count = 0
        for f in chunk_files:
            with open(f) as file:
                record_count += sum(1 for _ in file)
        
        return {
            "data_type": self.data_type,
            "chunk_files": len(chunk_files),
            "total_size_bytes": total_size,
            "record_count": record_count,
            "months": [f.stem.split("_")[1] for f in chunk_files]
        }
    
    def export_to_parquet(self, output_path: Optional[Path] = None) -> Optional[str]:
        """Export all data to Parquet for ML training."""
        try:
            import pandas as pd
            
            records = []
            for chunk_file in self.base_dir.glob(f"{self.data_type}_*.jsonl"):
                with open(chunk_file) as f:
                    for line in f:
                        records.append(json.loads(line))
            
            if records:
                df = pd.DataFrame(records)
                output = output_path or (self.base_dir / f"{self.data_type}_full.parquet")
                df.to_parquet(output, index=False)
                return str(output)
            
        except ImportError:
            return "Parquet export requires: pip install pyarrow pandas"
        
        return None


class DataCollector:
    """
    Main data collection orchestrator.
    Manages plot registration and coordinates periodic collection.
    """
    
    def __init__(self):
        self.registry = PlotRegistry()
        self._collection_task = None
        self._running = False
    
    def register_plot(self, farm_id: str, plot_id: str, coordinates: Dict, 
                      crop: str, area: float = 0) -> Dict:
        """
        Register a new plot for data collection.
        Called when a farmer creates a new plot.
        """
        plot_info = self.registry.register(farm_id, plot_id, coordinates, crop, area)
        
        # Log the registration event
        self._log_event("plot_registered", {
            "farm_id": farm_id,
            "plot_id": plot_id,
            "coordinates": coordinates,
            "crop": crop,
            "area": area
        })
        
        # Immediately capture initial snapshot
        self.capture_weather_snapshot(farm_id, plot_id)
        
        return plot_info
    
    def capture_weather_snapshot(self, farm_id: str, plot_id: str) -> Optional[Dict]:
        """
        Capture current weather conditions for a plot.
        Uses Open-Meteo API.
        """
        plot = self.registry.get_plot(farm_id, plot_id)
        if not plot:
            return None
        
        coords = plot["coordinates"]
        lat = coords.get("lat") or coords.get("latitude")
        lng = coords.get("lng") or coords.get("longitude")
        
        if not lat or not lng:
            return None
        
        try:
            import requests
            
            # Fetch current weather from Open-Meteo
            url = (
                f"https://api.open-meteo.com/v1/forecast?"
                f"latitude={lat}&longitude={lng}&"
                f"current=temperature_2m,relative_humidity_2m,precipitation,"
                f"windspeed_10m,surface_pressure,cloud_cover&"
                f"hourly=et0_fao_evapotranspiration&"
                f"timezone=auto"
            )
            
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                current = data.get("current", {})
                
                observation = {
                    "timestamp": datetime.now().isoformat(),
                    "plot_id": plot_id,
                    "farm_id": farm_id,
                    "temp": current.get("temperature_2m"),
                    "humidity": current.get("relative_humidity_2m"),
                    "rain": current.get("precipitation", 0),
                    "wind_speed": current.get("windspeed_10m"),
                    "pressure": current.get("surface_pressure"),
                    "cloud_cover": current.get("cloud_cover"),
                    "source": "open-meteo"
                }
                
                # Store in observation store
                store = ObservationStore(farm_id, plot_id, "weather")
                store.append(observation)
                
                # Update registry
                self.registry.update_collection_time(farm_id, plot_id, "weather")
                
                return observation
                
        except Exception as e:
            print(f"Weather collection error for {farm_id}/{plot_id}: {e}")
        
        return None
    
    def capture_satellite_snapshot(self, farm_id: str, plot_id: str) -> Optional[Dict]:
        """
        Capture satellite-derived vegetation indices.
        Uses existing Sentinel module.
        """
        plot = self.registry.get_plot(farm_id, plot_id)
        if not plot:
            return None
        
        coords = plot["coordinates"]
        lat = coords.get("lat") or coords.get("latitude")
        lng = coords.get("lng") or coords.get("longitude")
        
        if not lat or not lng:
            return None
        
        try:
            # Import the Sentinel module
            from eo.sentinel import SentinelClient
            
            client = SentinelClient()
            
            # Create a small bounding box around the point
            buffer = 0.005  # ~500m
            bbox = [lng - buffer, lat - buffer, lng + buffer, lat + buffer]
            
            # Get NDVI for the last 10 days
            end_date = datetime.now()
            start_date = end_date - timedelta(days=10)
            
            ndvi_data = client.fetch_ndvi_stats(
                bbox,
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d")
            )
            
            if ndvi_data:
                observation = {
                    "timestamp": datetime.now().isoformat(),
                    "plot_id": plot_id,
                    "farm_id": farm_id,
                    "ndvi_mean": ndvi_data.get("ndvi_mean"),
                    "ndvi_std": ndvi_data.get("ndvi_std"),
                    "cloud_cover": ndvi_data.get("cloud_cover", 0),
                    "acquisition_date": ndvi_data.get("date"),
                    "source": "sentinel-2"
                }
                
                store = ObservationStore(farm_id, plot_id, "ndvi")
                store.append(observation)
                
                self.registry.update_collection_time(farm_id, plot_id, "satellite")
                
                return observation
                
        except Exception as e:
            print(f"Satellite collection error for {farm_id}/{plot_id}: {e}")
        
        return None
    
    def collect_all_weather(self) -> Dict:
        """Collect weather for all active plots."""
        results = {"success": 0, "failed": 0, "plots": []}
        
        for plot in self.registry.get_active_plots():
            obs = self.capture_weather_snapshot(plot["farm_id"], plot["plot_id"])
            if obs:
                results["success"] += 1
                results["plots"].append(f"{plot['farm_id']}/{plot['plot_id']}")
            else:
                results["failed"] += 1
        
        return results
    
    def get_status(self) -> Dict:
        """Get overall collection status."""
        plots = self.registry.get_active_plots()
        
        total_observations = 0
        total_size = 0
        
        for plot in plots:
            plot_dir = OBSERVATIONS_DIR / plot["farm_id"] / plot["plot_id"]
            if plot_dir.exists():
                for f in plot_dir.glob("*.jsonl"):
                    total_size += f.stat().st_size
                    with open(f) as file:
                        total_observations += sum(1 for _ in file)
        
        return {
            "active_plots": len(plots),
            "total_observations": total_observations,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "plots": [
                {
                    "farm_id": p["farm_id"],
                    "plot_id": p["plot_id"],
                    "crop": p["crop"],
                    "collection_count": p.get("collection_count", 0),
                    "last_weather": p.get("last_weather_collection"),
                    "last_satellite": p.get("last_satellite_collection")
                }
                for p in plots
            ]
        }
    
    def get_plot_data(self, farm_id: str, plot_id: str, 
                      start_date: str = None, end_date: str = None) -> Dict:
        """Get all collected data for a plot."""
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).isoformat()
        if not end_date:
            end_date = datetime.now().isoformat()
        
        weather_store = ObservationStore(farm_id, plot_id, "weather")
        ndvi_store = ObservationStore(farm_id, plot_id, "ndvi")
        
        return {
            "farm_id": farm_id,
            "plot_id": plot_id,
            "period": {"start": start_date, "end": end_date},
            "weather": weather_store.query(start_date, end_date),
            "ndvi": ndvi_store.query(start_date, end_date),
            "weather_stats": weather_store.get_stats(),
            "ndvi_stats": ndvi_store.get_stats()
        }
    
    def _log_event(self, event_type: str, data: Dict):
        """Log a collection event."""
        event_file = EVENTS_DIR / f"{event_type}.jsonl"
        event = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            **data
        }
        with open(event_file, "a") as f:
            f.write(json.dumps(event) + "\n")


# Global instance
data_collector = DataCollector()
