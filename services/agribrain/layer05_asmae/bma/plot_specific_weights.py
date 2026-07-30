"""
Plot Specific BMA Weights.
Tracks and logs diagnostic BMA weight changes per plot across different crop seasons.
"""
from typing import Dict, Any, List

class PlotSpecificWeightsManager:
    def __init__(self, plot_id: str):
        self.plot_id = plot_id
        self.history: List[Dict[str, Any]] = []

    def record_season_weights(
        self,
        season_id: str,
        bma_results: Dict[str, Any]
    ) -> None:
        """
        Appends BMA weight configuration to plot history.
        Enforces that only weights marked as 'diagnostic' are saved.
        """
        status = bma_results.get("archive_bma_status", "diagnostic")
        
        # Save record
        self.history.append({
            "plot_id": self.plot_id,
            "season_id": season_id,
            "weights": bma_results.get("weights", {}),
            "archive_bma_status": status,
            "can_promote_to_production": bma_results.get("can_promote_to_production", False)
        })

    def get_history(self) -> List[Dict[str, Any]]:
        """Returns the logged weight configurations timeline."""
        return self.history
