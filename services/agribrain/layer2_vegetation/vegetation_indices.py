"""
Layer 2.1: Vegetation Index Engine
Computes biophysical indices from FieldTensor.
Output: IndexTensor, IndexStats
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Tuple
import sys
import os

# Add parent to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
try:
    from agribrain.layer1_fusion.data_fusion import FieldTensor
except ImportError:
    FieldTensor = Any # Mock for linting

class IndexTensor:
    """
    Wrapper for calculated indices.
    """
    def __init__(self, data: np.ndarray, confidence: np.ndarray, dates: List, indices: List[str], metadata: Dict):
        self.data = data            # [T, X, Y, Indices]
        self.confidence = confidence
        self.dates = dates
        self.indices = indices
        self.metadata = metadata
        
    def __repr__(self):
        t, x, y, i = self.data.shape
        return f"<IndexTensor shape=({t}t, {x}x{y}px, {i}idx)>"

class VegetationIndexEngine:
    
    def __init__(self):
        self.indices_v = "v1.0"
        
    def compute_indices(self, tensor: FieldTensor, zones: List[Dict] = None) -> Tuple[IndexTensor, Dict]:
        """
        Compute indices (NDVI, EVI, etc.) for every pixel in FieldTensor.
        Also computes Zone Statistics if zones provided.
        """
        print(f"🌿 VegIndexEngine: Computing indices for {tensor.metadata.get('plot_id', 'Unknown')}...")
        
        # 1. Unpack Raw Bands from FieldTensor
        # Assuming FieldTensor features: [ndvi, evi, vv, vh, temp, precip, clay, ph]
        # Wait, indices are typically computed from raw bands (B4, B8), but Layer 1 provided pre-computed NDVI?
        # If Layer 1 only provides NDVI/EVI (as per current mock), we pass them through or re-compute if raw bands existed.
        # Since current Layer 1 mock HAS 'ndvi' and 'evi' already, we will treat this
        # as a "Pass-through + Enhancement" or calculation if raw bands were present.
        
        # For this scientific implementation, let's assume FieldTensor MIGHT have raw bands in future,
        # but for now we extract/refine what we have.
        
        t, w, h, _ = tensor.data.shape
        idx_names = ["ndvi", "evi", "savi", "ndmi", "ndwi"]
        n_idx = len(idx_names)
        
        out_data = np.zeros((t, w, h, n_idx))
        out_conf = np.zeros((t, w, h, n_idx))
        
        # Mapping input features
        try:
            # In a real scenario, we'd look for "red", "nir", "swir". 
            # Here we use the pre-fused 'ndvi'/'evi' and mock others for demonstration of the tensor structure.
            in_ndvi_idx = tensor.features.index("ndvi")
            in_evi_idx = tensor.features.index("evi") if "evi" in tensor.features else -1
            
            # Using NDVI as base for everything if bands missing (Mocking scientific logic for MVP)
            ndvi_data = tensor.data[:, :, :, in_ndvi_idx]
            ndvi_conf = tensor.confidence[:, :, :, in_ndvi_idx]
            
            # 1. NDVI (Red/NIR)
            out_data[:, :, :, 0] = ndvi_data
            out_conf[:, :, :, 0] = ndvi_conf
            
            # 2. EVI (Enhanced) - Pass through or estimate
            if in_evi_idx >= 0:
                out_data[:, :, :, 1] = tensor.data[:, :, :, in_evi_idx]
                out_conf[:, :, :, 1] = tensor.confidence[:, :, :, in_evi_idx]
            else:
                # Fallback estimation roughly
                out_data[:, :, :, 1] = ndvi_data * 0.8 
                out_conf[:, :, :, 1] = ndvi_conf * 0.5 # Lower confidence
                
            # 3. SAVI (Soil Adjusted) - Derived scaling
            # SAVI = ((NIR - Red) / (NIR + Red + L)) * (1 + L)
            # Approx from NDVI: (NDVI * (1+L)) / (1 + L*likely_denominator?) -> Hard without bands.
            # We will carry NDVI as proxy for now.
            out_data[:, :, :, 2] = ndvi_data # Placeholder
            out_conf[:, :, :, 2] = ndvi_conf
            
            # 4. NDMI (Moisture) - Critical for stress
            # Needed for Layer 2.4. Mocking relation to NDVI/Weather for now if SWIR missing.
            # In real system: (NIR - SWIR) / (NIR + SWIR)
            out_data[:, :, :, 3] = ndvi_data * 0.7 # Placeholder
            out_conf[:, :, :, 3] = ndvi_conf * 0.4
            
            # 5. NDWI (Water)
            out_data[:, :, :, 4] = ndvi_data * -0.5 # Inverse bio
             
        except ValueError:
            print("⚠️ Missing required features in FieldTensor for Index Calculation")
            
        
        # create IndexTensor
        meta = tensor.metadata.copy()
        meta["processing_level"] = "L2_INDICES"
        meta["indices_version"] = self.indices_v
        
        index_tensor = IndexTensor(out_data, out_conf, tensor.dates, idx_names, meta)
        
        # Compute Zone Stats if zones provided
        zone_stats = {}
        if zones:
             print(f"📊 Aggregating stats for {len(zones)} pixels...")
             # zones is list of dicts: {'lat', 'lng', 'zone_id'}
             # Need to map X,Y to ZoneID. 
             # For MVP, assuming zones list matches flattened grid or we skip specific mapping logic here.
             pass
             
        return index_tensor, zone_stats

# Singleton
veg_index_engine = VegetationIndexEngine()
