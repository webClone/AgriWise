"""
Archive Metrics Store.
Manages saving and loading historical, retrovalidation, BMA, and baseline metrics
under a dedicated directory path:
services/agribrain/artifacts/archive_metrics/{plot_id}/{geometry_hash}/{archive_run_id}/
"""
import os
import json
import tempfile
from typing import Dict, Any, Optional

from pathlib import Path

class ArchiveMetricsStore:
    def __init__(self, workspace_root=None, agribrain_root=None, metrics_root=None):
        if metrics_root is not None:
            self.metrics_root = str(Path(metrics_root).resolve())
            self.workspace_root = workspace_root or str(Path(self.metrics_root).parents[2])
            return

        if agribrain_root is not None:
            self.metrics_root = str(
                Path(agribrain_root).resolve() / "artifacts" / "archive_metrics"
            )
            self.workspace_root = workspace_root or str(Path(agribrain_root).resolve().parent)
            return

        if workspace_root is not None:
            self.workspace_root = str(Path(workspace_root).resolve())
            self.metrics_root = str(
                Path(workspace_root).resolve()
                / "services"
                / "agribrain"
                / "artifacts"
                / "archive_metrics"
            )
            return

        agribrain_root = Path(__file__).resolve().parents[2]
        self.metrics_root = str(agribrain_root / "artifacts" / "archive_metrics")
        self.workspace_root = str(agribrain_root.parent)

    def _get_dir(self, plot_id: str, geometry_hash: str, archive_run_id: str) -> str:
        if ".." in plot_id or "/" in plot_id or "\\" in plot_id:
            raise ValueError(f"Invalid characters in plot_id: {plot_id}")
        if ".." in geometry_hash or "/" in geometry_hash or "\\" in geometry_hash:
            raise ValueError(f"Invalid characters in geometry_hash: {geometry_hash}")
        if ".." in archive_run_id or "/" in archive_run_id or "\\" in archive_run_id:
            raise ValueError(f"Invalid characters in archive_run_id: {archive_run_id}")
        return os.path.join(self.metrics_root, plot_id, geometry_hash, archive_run_id)

    def _write_json_atomically(self, dir_path: str, filename: str, data: Dict[str, Any]) -> None:
        os.makedirs(dir_path, exist_ok=True)
        file_path = os.path.join(dir_path, filename)
        fd, temp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
        os.close(fd)
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(temp_path, file_path)
        except Exception as e:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            raise e

    def save_all_metrics(
        self,
        plot_id: str,
        geometry_hash: str,
        archive_run_id: str,
        historical: Dict[str, Any],
        retrovalidation: Dict[str, Any],
        archive_bma: Dict[str, Any],
        baseline: Dict[str, Any],
        archive_posterior: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Saves all 4 types of metrics atomically under the dedicated path."""
        dir_path = self._get_dir(plot_id, geometry_hash, archive_run_id)
        self._write_json_atomically(dir_path, "historical_metrics.json", historical)
        self._write_json_atomically(dir_path, "retrovalidation_metrics.json", retrovalidation)
        self._write_json_atomically(dir_path, "archive_bma_metrics.json", archive_bma)
        self._write_json_atomically(dir_path, "baseline_metrics.json", baseline)
        if archive_posterior is not None:
            self._write_json_atomically(
                dir_path, "archive_posterior.json", archive_posterior
            )

    def load_metrics_file(
        self,
        plot_id: str,
        geometry_hash: str,
        archive_run_id: str,
        filename: str
    ) -> Optional[Dict[str, Any]]:
        """Loads a metrics JSON file if exists, otherwise returns None."""
        dir_path = self._get_dir(plot_id, geometry_hash, archive_run_id)
        file_path = os.path.join(dir_path, filename)
        if not os.path.exists(file_path):
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            # Propagate malformed JSON error instead of silent fallback
            raise ValueError(f"Malformed JSON in metrics file: {file_path}")

    def get_latest_metrics_info(self, plot_id: str) -> Optional[Dict[str, Any]]:
        """
        Scans artifacts/archive_metrics/{plot_id}/ recursively.
        Returns a dict containing metrics hash, run_id, geometry_hash, and data.
        """
        import hashlib
        plot_dir = os.path.join(self.metrics_root, plot_id)
        if not os.path.exists(plot_dir) or not os.path.isdir(plot_dir):
            return None
            
        # Find all historical_metrics.json files
        candidates = []
        for root, dirs, files in os.walk(plot_dir):
            if "historical_metrics.json" in files:
                file_path = os.path.join(root, "historical_metrics.json")
                mtime = os.path.getmtime(file_path)
                candidates.append((mtime, root))
                
        if not candidates:
            return None
            
        # Pick the latest modified one
        candidates.sort(reverse=True)
        latest_root = candidates[0][1]
        
        # Extract geometry_hash and archive_run_id from path
        parts = os.path.normpath(latest_root).split(os.sep)
        try:
            plot_idx = parts.index(plot_id)
            geom_hash = parts[plot_idx + 1]
            run_id = parts[plot_idx + 2]
        except (ValueError, IndexError):
            geom_hash = "unknown_geom"
            run_id = "unknown_run"
            
        # Read the 4 JSON files and compute a combined hash
        hasher = hashlib.sha256()
        files_to_hash = ["historical_metrics.json", "retrovalidation_metrics.json", "archive_bma_metrics.json", "baseline_metrics.json"]
        
        loaded_data = {}
        for f_name in files_to_hash:
            f_path = os.path.join(latest_root, f_name)
            if not os.path.exists(f_path):
                return None
            try:
                with open(f_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    parsed = json.loads(content)
                    loaded_data[f_name.replace(".json", "")] = parsed
                    hasher.update(content.encode("utf-8"))
            except Exception:
                raise ValueError(f"Malformed JSON in metrics file: {f_path}")

        # The certified posterior is optional for legacy archive runs.  When
        # present it participates in archive identity and is exposed to the
        # live resilient path; metadata-only metric bundles cannot impersonate
        # it.
        posterior_path = os.path.join(latest_root, "archive_posterior.json")
        if os.path.exists(posterior_path):
            try:
                with open(posterior_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    loaded_data["archive_posterior"] = json.loads(content)
                    hasher.update(content.encode("utf-8"))
            except Exception:
                raise ValueError(
                    f"Malformed JSON in metrics file: {posterior_path}"
                )
                
        metrics_hash = hasher.hexdigest()
        
        hist_data = loaded_data.get("historical_metrics", {})
        bma_data = loaded_data.get("archive_bma_metrics", {})
        retro_data = loaded_data.get("retrovalidation_metrics", {})
        base_data = loaded_data.get("baseline_metrics", {})
        
        return {
            "archive_run_id": run_id,
            "geometry_hash": geom_hash,
            "archive_metrics_hash": metrics_hash,
            "archive_policy_version": hist_data.get("archive_policy_version", "v90_7_1_archive_policy"),
            "retrovalidation_policy_version": retro_data.get("retrovalidation_policy_version", "v90_7_1_retrovalidation_policy"),
            "archive_bma_policy_version": bma_data.get("archive_bma_policy_version", "v90_7_1_bma_policy"),
            "baseline_policy_version": base_data.get("baseline_policy_version", "v90_7_1_baseline_policy"),
            "data": loaded_data
        }
