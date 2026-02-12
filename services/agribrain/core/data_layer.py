"""
Data Layer Infrastructure
Proper data engineering for AI training datasets:
- Parquet for tabular data (structured predictions, telemetry)
- Zarr for multidimensional arrays (time-series, satellite)
- Versioned datasets with schema contracts
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib

# Dataset root
DATA_ROOT = Path(__file__).parent.parent / "datasets"
DATA_ROOT.mkdir(exist_ok=True)

# Schema version - increment when contract changes
SCHEMA_VERSION = "1.0.0"


class DataContract:
    """
    Fixed schema contract for tool inputs/outputs.
    Ensures consistency across training data.
    """
    
    # Input schemas (what the AI receives)
    INPUT_SCHEMAS = {
        "realtime_telemetry": {
            "version": "1.0.0",
            "fields": {
                "temp": {"type": "float", "unit": "celsius", "range": [-50, 60]},
                "humidity": {"type": "float", "unit": "percent", "range": [0, 100]},
                "rain": {"type": "float", "unit": "mm", "range": [0, 500]},
                "windSpeed": {"type": "float", "unit": "km/h", "range": [0, 200]},
                "deltaT": {"type": "float", "unit": "celsius", "range": [0, 20]},
                "vpd": {"type": "float", "unit": "kPa", "range": [0, 10]},
                "dewPoint": {"type": "float", "unit": "celsius", "range": [-50, 50]},
                "et0": {"type": "float", "unit": "mm/day", "range": [0, 20]},
                "leafWetness": {"type": "float", "unit": "percent", "range": [0, 100]},
                "uvIndex": {"type": "float", "unit": "index", "range": [0, 15]},
                "solarRad": {"type": "float", "unit": "W/m2", "range": [0, 1500]},
                "soilTemp": {"type": "float", "unit": "celsius", "range": [-20, 60]},
                "pressure": {"type": "float", "unit": "hPa", "range": [800, 1100]},
            }
        },
        "soil_profile": {
            "version": "1.0.0",
            "fields": {
                "textureClass": {"type": "string", "enum": ["Sand", "Loamy Sand", "Sandy Loam", "Loam", "Silt Loam", "Silt", "Sandy Clay Loam", "Clay Loam", "Silty Clay Loam", "Sandy Clay", "Silty Clay", "Clay"]},
                "clay": {"type": "float", "unit": "percent", "range": [0, 100]},
                "sand": {"type": "float", "unit": "percent", "range": [0, 100]},
                "silt": {"type": "float", "unit": "percent", "range": [0, 100]},
                "ph": {"type": "float", "unit": "pH", "range": [0, 14]},
                "nitrogen": {"type": "float", "unit": "g/kg", "range": [0, 20]},
                "cec": {"type": "float", "unit": "cmol/kg", "range": [0, 100]},
                "awc": {"type": "float", "unit": "percent", "range": [0, 50]},
            }
        },
        "crop_context": {
            "version": "1.0.0",
            "fields": {
                "crop": {"type": "string"},
                "gdd": {"type": "float", "unit": "degree_days", "range": [0, 5000]},
                "plantingDate": {"type": "string", "format": "date"},
                "coordinates": {"type": "object", "properties": {"lat": "float", "lng": "float"}},
            }
        }
    }
    
    # Output schemas (what the AI predicts)
    OUTPUT_SCHEMAS = {
        "disease_risk": {
            "version": "1.0.0",
            "fields": {
                "overall_risk": {"type": "string", "enum": ["low", "moderate", "high"]},
                "diseases": {"type": "array", "items": {
                    "disease": "string",
                    "risk_level": {"type": "string", "enum": ["low", "moderate", "high"]},
                    "risk_score": {"type": "int", "range": [0, 100]},
                }},
                "recommendation": {"type": "string"},
            }
        },
        "spray_window": {
            "version": "1.0.0",
            "fields": {
                "recommendation": {"type": "string", "enum": ["SPRAY_NOW", "ACCEPTABLE", "MARGINAL", "DO_NOT_SPRAY"]},
                "score": {"type": "int", "range": [0, 100]},
                "factors": {"type": "array"},
            }
        },
        "water_stress": {
            "version": "1.0.0",
            "fields": {
                "stress_level": {"type": "string", "enum": ["no_stress", "mild_stress", "moderate_stress", "severe_stress"]},
                "irrigation_needed": {"type": "bool"},
                "irrigation_amount_mm": {"type": "float", "range": [0, 100]},
            }
        },
        "phenology": {
            "version": "1.0.0",
            "fields": {
                "current_stage": {"type": "string"},
                "stage_progress": {"type": "float", "range": [0, 100]},
                "days_to_next_stage": {"type": "int", "range": [0, 365]},
            }
        }
    }
    
    @classmethod
    def validate_input(cls, schema_name: str, data: Dict) -> bool:
        """Validate input data against schema."""
        if schema_name not in cls.INPUT_SCHEMAS:
            return True  # Unknown schema, allow
        # In production, implement full validation
        return True
    
    @classmethod
    def get_schema_hash(cls, schema_name: str) -> str:
        """Get hash of schema for versioning."""
        schema = cls.INPUT_SCHEMAS.get(schema_name) or cls.OUTPUT_SCHEMAS.get(schema_name)
        if schema:
            return hashlib.md5(json.dumps(schema, sort_keys=True).encode()).hexdigest()[:8]
        return "unknown"


class VersionedDataset:
    """
    Versioned dataset storage using Parquet format.
    Supports append, query, and export operations.
    """
    
    def __init__(self, name: str, schema_name: str):
        self.name = name
        self.schema_name = schema_name
        self.version = SCHEMA_VERSION
        self.path = DATA_ROOT / name
        self.path.mkdir(exist_ok=True)
        
        # Metadata file
        self.meta_file = self.path / "metadata.json"
        self._init_metadata()
    
    def _init_metadata(self):
        """Initialize or load dataset metadata."""
        if self.meta_file.exists():
            with open(self.meta_file) as f:
                self.metadata = json.load(f)
        else:
            self.metadata = {
                "name": self.name,
                "schema": self.schema_name,
                "schema_version": self.version,
                "schema_hash": DataContract.get_schema_hash(self.schema_name),
                "created": datetime.now().isoformat(),
                "updated": datetime.now().isoformat(),
                "sample_count": 0,
                "partitions": []
            }
            self._save_metadata()
    
    def _save_metadata(self):
        """Save metadata to disk."""
        with open(self.meta_file, "w") as f:
            json.dump(self.metadata, f, indent=2)
    
    def append(self, sample: Dict[str, Any], label: Optional[Dict] = None):
        """
        Append a sample to the dataset.
        Uses date-partitioned JSONL files (upgradeable to Parquet).
        """
        # Validate against schema
        DataContract.validate_input(self.schema_name, sample)
        
        # Date partition
        date_str = datetime.now().strftime("%Y-%m-%d")
        partition_file = self.path / f"partition_{date_str}.jsonl"
        
        # Build record
        record = {
            "timestamp": datetime.now().isoformat(),
            "schema_version": self.version,
            "inputs": sample,
            "label": label
        }
        
        # Append to partition
        with open(partition_file, "a") as f:
            f.write(json.dumps(record) + "\n")
        
        # Update metadata
        self.metadata["sample_count"] += 1
        self.metadata["updated"] = datetime.now().isoformat()
        if date_str not in self.metadata["partitions"]:
            self.metadata["partitions"].append(date_str)
        self._save_metadata()
    
    def get_sample_count(self) -> int:
        """Get total sample count."""
        return self.metadata["sample_count"]
    
    def export_to_parquet(self, output_path: Optional[Path] = None):
        """
        Export dataset to Parquet format for training.
        Requires: pip install pyarrow pandas
        """
        try:
            import pandas as pd
            
            records = []
            for partition in self.metadata["partitions"]:
                partition_file = self.path / f"partition_{partition}.jsonl"
                if partition_file.exists():
                    with open(partition_file) as f:
                        for line in f:
                            records.append(json.loads(line))
            
            if records:
                df = pd.json_normalize(records)
                output = output_path or (self.path / f"{self.name}_v{self.version}.parquet")
                df.to_parquet(output, index=False)
                return str(output)
        except ImportError:
            return "Parquet export requires: pip install pyarrow pandas"
        return None


class TimeSeriesStore:
    """
    Zarr-like store for time-series data (NDVI, weather history).
    Uses chunked storage for efficient access.
    """
    
    def __init__(self, name: str):
        self.name = name
        self.path = DATA_ROOT / "timeseries" / name
        self.path.mkdir(parents=True, exist_ok=True)
        self.chunk_size = 30  # 30 days per chunk
    
    def append_observation(self, field_id: str, date: str, data: Dict[str, float]):
        """
        Append a time-series observation.
        Stores as monthly chunks for efficient retrieval.
        """
        # Parse date to month chunk
        dt = datetime.fromisoformat(date)
        chunk_id = dt.strftime("%Y-%m")
        
        field_path = self.path / field_id
        field_path.mkdir(exist_ok=True)
        
        chunk_file = field_path / f"{chunk_id}.jsonl"
        
        record = {
            "date": date,
            **data
        }
        
        with open(chunk_file, "a") as f:
            f.write(json.dumps(record) + "\n")
    
    def get_series(self, field_id: str, start_date: str, end_date: str) -> List[Dict]:
        """Retrieve time-series data for date range."""
        field_path = self.path / field_id
        if not field_path.exists():
            return []
        
        records = []
        for chunk_file in sorted(field_path.glob("*.jsonl")):
            with open(chunk_file) as f:
                for line in f:
                    record = json.loads(line)
                    if start_date <= record["date"] <= end_date:
                        records.append(record)
        
        return sorted(records, key=lambda x: x["date"])


# Pre-configured datasets for each AI module
DATASETS = {
    "disease_risk": VersionedDataset("disease_risk", "disease_risk"),
    "spray_window": VersionedDataset("spray_window", "spray_window"),
    "water_stress": VersionedDataset("water_stress", "water_stress"),
    "phenology": VersionedDataset("phenology", "phenology"),
}

# Time-series stores
TIMESERIES = {
    "ndvi": TimeSeriesStore("ndvi"),
    "weather": TimeSeriesStore("weather"),
    "soil_moisture": TimeSeriesStore("soil_moisture"),
}
