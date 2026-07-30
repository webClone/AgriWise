"""
Layer 1.4: Zonal Segmentation Engine
Clusters field data into management zones (High/Medium/Low performance).
"""

import numpy as np
from sklearn.cluster import KMeans, GaussianMixture
from sklearn.metrics import silhouette_score
from typing import List, Dict, Any

class ZonalSegmentationEngine:
    """
    Segments a field into homogeneous management zones.
    """
    
    def __init__(self, n_zones: int = 3):
        self.n_zones = n_zones
        self.model = KMeans(n_clusters=n_zones, random_state=42)
        
    def find_optimal_k(self, X: np.ndarray, max_k: int = 5) -> int:
        """
        Determine optimal K using BIC (Bayesian Information Criterion) and Silhouette Score.
        """
        if len(X) < 10:
            return 3 # Not enough data
            
        bics = []
        silhouettes = []
        
        for k in range(2, max_k + 1):
            gmm = GaussianMixture(n_components=k, random_state=42)
            gmm.fit(X)
            bics.append(gmm.bic(X))
            
            labels = gmm.predict(X)
            # Silhouette only defined if > 1 label exists
            if len(np.unique(labels)) > 1:
                try:
                    score = silhouette_score(X, labels)
                    silhouettes.append(score)
                except:
                    silhouettes.append(-1)
            else:
                silhouettes.append(-1)
                
        # Heuristic: Min BIC is good, but check Silhouette
        best_k_bic = np.argmin(bics) + 2
        best_k_sil = np.argmax(silhouettes) + 2
        
        print(f"🧐 Zoning Analysis: Best K (BIC)={best_k_bic}, Best K (Sil)={best_k_sil}")
        
        # Prefer Silhouette for spatial distinctness if reasonable
        return best_k_sil

    def segment_field(self, pixels: List[Dict[str, float]], method: str = 'kmeans', auto_k: bool = True) -> List[Dict[str, Any]]:
        """
        Segments field pixels into zones.
        Methods: 'kmeans' (Hard), 'gmm' (Soft).
        Flags: auto_k=True will calculate optimal zones.
        """
        if not pixels:
            return []
            
        # Extract features matrix
        features = []
        for p in pixels:
            # Feature vector: [Mean NDVI, Stability (1/std)]
            ndvi = p.get('mean_ndvi', 0)
            stability = 1.0 / (p.get('std_ndvi', 1.0) + 0.01)
            features.append([ndvi, stability])
            
        X = np.array(features)
        
        # Determine K
        k = self.n_zones
        if auto_k and len(X) > 10:
            try:
                k = self.find_optimal_k(X)
                self.n_zones = k # Update state
            except Exception as e:
                print(f"[WARN] Auto-K failed: {e}")
                
        # Fit logic
        labels = np.zeros(len(X))
        if len(X) >= k:
            if method == 'gmm':
                gmm = GaussianMixture(n_components=k, random_state=42)
                labels = gmm.fit_predict(X)
            else:
                kmeans = KMeans(n_clusters=k, random_state=42)
                labels = kmeans.fit_predict(X)
            
        # Rank Logic (Low -> High)
        cluster_means = []
        for i in range(k):
            mask = labels == i
            if np.any(mask):
                mean_val = X[mask][:, 0].mean() 
                cluster_means.append((i, mean_val))
            else:
                cluster_means.append((i, 0))
            
        cluster_means.sort(key=lambda x: x[1])
        rank_map = {old: new for new, (old, _) in enumerate(cluster_means)}
        
        # Qualitative Labels
        zone_names = {0: "Low Vigor", 1: "Average", 2: "High Vigor", 3: "Elite"}
            
        result = []
        for i, p in enumerate(pixels):
            raw_label = labels[i]
            ranked_label = rank_map.get(raw_label, 0)
            
            p_out = p.copy()
            p_out['zone_id'] = int(ranked_label)
            p_out['zone_name'] = zone_names.get(ranked_label, f"Zone {ranked_label}")
            p_out['method'] = method
            result.append(p_out)
            
        return result

# Singleton
segmentation_engine = ZonalSegmentationEngine()
