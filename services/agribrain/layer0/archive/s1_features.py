"""
Sentinel-1 SAR Features.
Computes polarization indices (RVI, NDPI, ratio) from VV and VH backscatter bands.
Enforces safe division.
"""
import numpy as np

class S1Features:
    def __init__(self):
        pass

    def _to_linear(self, db_array: np.ndarray) -> np.ndarray:
        return 10.0 ** (db_array / 10.0)

    def compute_rvi(self, vv_db: np.ndarray, vh_db: np.ndarray) -> np.ndarray:
        """
        Computes dual-pol Radar Vegetation Index (RVI):
        RVI = (4.0 * VH_linear) / (VV_linear + VH_linear)
        """
        vv_lin = self._to_linear(vv_db)
        vh_lin = self._to_linear(vh_db)
        
        denominator = vv_lin + vh_lin
        safe_denom = np.where(denominator > 0.0, denominator, 1.0)
        
        rvi = np.where(
            denominator > 0.0,
            (4.0 * vh_lin) / safe_denom,
            0.0
        )
        return np.clip(rvi, 0.0, 2.0)

    def compute_ndpi(self, vv_db: np.ndarray, vh_db: np.ndarray) -> np.ndarray:
        """
        Computes Normalized Difference Polarimetric Index (NDPI):
        NDPI = (VV_linear - VH_linear) / (VV_linear + VH_linear)
        """
        vv_lin = self._to_linear(vv_db)
        vh_lin = self._to_linear(vh_db)
        
        denominator = vv_lin + vh_lin
        safe_denom = np.where(denominator > 0.0, denominator, 1.0)
        
        ndpi = np.where(
            denominator > 0.0,
            (vv_lin - vh_lin) / safe_denom,
            0.0
        )
        return np.clip(ndpi, -1.0, 1.0)

    def compute_cross_ratio_db(self, vv_db: np.ndarray, vh_db: np.ndarray) -> np.ndarray:
        """
        Computes VV/VH ratio in decibel scale (which is VV_db - VH_db).
        """
        return vv_db - vh_db
