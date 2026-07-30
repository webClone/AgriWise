"""
Pattern ⑦ — Temporal Attention Encoder.

Implements a temporal self-attention mechanism over PlotObservation timeseries
data to identify key historical phenological inflection points. Automatically
falls back to an exponentially weighted moving average (EMA) when data density
is low or models are not loaded.
"""

from __future__ import annotations

import math
import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("agribrain.learning.temporal_attention")


class TemporalAttention:
    """Computes phenological self-attention weights over historical timeseries."""

    def __init__(self, d_model: int = 4, fallback_alpha: float = 0.2):
        self.d_model = d_model
        self.fallback_alpha = fallback_alpha
        # Simplified learned linear projections for Q, K, V
        self.W_q = [1.0, 0.5, 0.2, 0.1]
        self.W_k = [1.0, 0.4, 0.3, 0.1]
        self.W_v = [1.0, 0.8, 0.5, 0.2]

    def compute_attention(self, timeseries: List[Dict[str, Any]], variable: str) -> List[Dict[str, Any]]:
        """Compute self-attention over timeseries observations.
        
        Returns a list of observations enriched with attention weights.
        """
        n = len(timeseries)
        if n < 5:
            # Fallback to EMA when data points are sparse
            logger.debug("[TEMP_ATTN] Low timeseries density (%d points). Falling back to EMA.", n)
            return self._compute_ema_fallback(timeseries, variable)

        # 1. Extract feature vectors (representing [value, age, quality, anomaly])
        features: List[List[float]] = []
        for i, obs in enumerate(timeseries):
            val = float(obs.get(variable) or obs.get("features", {}).get(variable) or 0.0)
            age = float(i) / n
            quality = float(obs.get("quality", 1.0))
            anomaly = float(obs.get("anomaly_score", 0.0))
            features.append([val, age, quality, anomaly])

        # 2. Compute Q, K, V vectors (scalar products for simplified attention)
        Q = [sum(f[c] * self.W_q[c] for c in range(self.d_model)) for f in features]
        K = [sum(f[c] * self.W_k[c] for c in range(self.d_model)) for f in features]
        V = [sum(f[c] * self.W_v[c] for c in range(self.d_model)) for f in features]

        # 3. Scaled dot-product attention
        # score(i, j) = Q[i] * K[j] / sqrt(d_model)
        scale = math.sqrt(self.d_model)
        scores = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                scores[i][j] = (Q[i] * K[j]) / scale

        # Softmax over columns
        weights = [[0.0] * n for _ in range(n)]
        for i in range(n):
            row_max = max(scores[i])
            row_exp = []
            for j in range(n):
                try:
                    row_exp.append(math.exp(scores[i][j] - row_max))
                except OverflowError:
                    row_exp.append(0.0)
            
            sum_exp = sum(row_exp) or 1.0
            for j in range(n):
                weights[i][j] = row_exp[j] / sum_exp

        # 4. Compute weighted context outputs
        results = []
        for i in range(n):
            context_val = sum(weights[i][j] * V[j] for j in range(n))
            # Average attention weight received by observation i
            avg_attn_weight = sum(weights[j][i] for j in range(n)) / n
            
            results.append({
                **timeseries[i],
                "attention_weight": round(avg_attn_weight, 4),
                "context_value": round(context_val, 4)
            })

        return results

    def _compute_ema_fallback(self, timeseries: List[Dict[str, Any]], variable: str) -> List[Dict[str, Any]]:
        """Fallback exponential moving average."""
        results = []
        running_ema = 0.0
        for i, obs in enumerate(timeseries):
            val = float(obs.get(variable) or obs.get("features", {}).get(variable) or 0.0)
            if i == 0:
                running_ema = val
            else:
                running_ema = self.fallback_alpha * val + (1.0 - self.fallback_alpha) * running_ema

            # Simulated linear decay proxy for attention weights under EMA
            results.append({
                **obs,
                "attention_weight": round(1.0 / len(timeseries), 4),
                "context_value": round(running_ema, 4)
            })
        return results
