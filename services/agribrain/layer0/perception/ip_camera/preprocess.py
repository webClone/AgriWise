"""
IP Camera Preprocessor — frame loading, ROI masking, segmentation, and stat extraction.

Dual-path design (same pattern as farmer_photo/preprocess.py):
  - Real path: loads frame via OpenCV, segments crop/soil/sky, extracts per-region
    stats, computes histogram descriptors, generates tensors
  - Mock path: reads mock_frame_stats from metadata (for tests without cv2)

The mock path is NOT a placeholder — it is the permanent test/benchmark interface.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import os

try:
    import numpy as np
    import cv2
    HAS_CV2 = True
except ImportError:
    np = None  # type: ignore
    cv2 = None  # type: ignore
    HAS_CV2 = False

from layer0.perception.ip_camera.schemas import IPCameraEngineInput


@dataclass
class PreprocessResult:
    """All extracted stats from a single IP camera frame."""

    # Channel ratios (sum to ~1.0)
    green_ratio: float = 0.33
    red_ratio: float = 0.33
    blue_ratio: float = 0.33

    # Derived color features
    yellow_ratio: float = 0.0
    brown_ratio: float = 0.0

    # Brightness / exposure (full frame)
    brightness_mean: float = 128.0
    brightness_std: float = 30.0
    saturation_mean: float = 100.0
    overexposed_pct: float = 0.0
    underexposed_pct: float = 0.0

    # Sharpness
    laplacian_var: Optional[float] = None

    # Coverage fractions from segmentation
    green_coverage_fraction: float = 0.0  # fraction of pixels classified as vegetation
    soil_fraction: float = 0.0
    sky_fraction: float = 0.0

    # Per-region stats (crop region only)
    crop_region_green_ratio: float = 0.33
    crop_region_brightness: float = 128.0
    crop_region_saturation: float = 100.0

    # Structural descriptors
    edge_density: float = 0.0            # Canny edge pixel fraction
    hsv_histogram: Optional[Any] = None  # normalized HSV histogram for baseline comparison

    # Spatial shift (estimated via template match against baseline)
    shift_x: float = 0.0
    shift_y: float = 0.0

    # Per-tile Laplacian stats (for rain-on-lens detection)
    tile_laplacian_values: Optional[List[float]] = None

    # Quadrant brightness (for spatial uniformity)
    quadrant_brightness: Optional[List[float]] = None

    # Downsampled gray thumbnail (for stale-frame SSIM)
    gray_thumbnail_64: Optional[Any] = None  # 64x64 uint8

    # Phenology (heuristic, not from image directly in V1)
    phenology_stage_est: float = 2.0

    # Image metadata
    width: int = 0
    height: int = 0

    # Real-image state
    real_image_loaded: bool = False
    load_error: str = ""

    # Segmentation masks (only populated when cv2 is available)
    crop_mask: Optional[Any] = None          # binary uint8 mask
    resized_tensor: Optional[Any] = None     # float32 NCHW [0,1] RGB 224x224
    image_rgb_uint8: Optional[Any] = None    # original size RGB uint8


class IPCameraPreprocessor:
    """
    Prepares the raw frame for inference.
    - Loads image from frame_ref or raw bytes
    - Applies ROI mask from calibration (polygon)
    - Segments crop / soil / sky via HSV thresholding
    - Extracts per-region pixel statistics for QA, inference, and baseline
    - Computes histogram descriptor for baseline comparison
    - Falls back to mock_frame_stats for testing
    """

    def process(self, input_data: IPCameraEngineInput) -> Tuple[PreprocessResult, dict]:
        """Returns a PreprocessResult and a context dictionary."""
        result = PreprocessResult()
        context = {
            "lighting_normalized": False,
            "crop_mask_applied": False,
            "roi_applied": False,
            "segmentation_applied": False,
            "source": "mock",
        }

        # --- Path 1: Try real image loading ---
        frame_ref = input_data.frame_ref or ""
        frame_bytes = input_data.metadata.get("frame_bytes")

        if (frame_ref or frame_bytes) and HAS_CV2:
            self._load_real_image(result, input_data, frame_ref, frame_bytes)
            if result.real_image_loaded:
                context["source"] = "cv2"
                context["lighting_normalized"] = True
                context["segmentation_applied"] = True
                context["crop_mask_applied"] = result.crop_mask is not None

                # Check if ROI was applied
                roi_poly = input_data.metadata.get("roi_polygon")
                if roi_poly:
                    context["roi_applied"] = True

        # --- Path 2: Mock fallback (tests / no cv2) ---
        if not result.real_image_loaded:
            mock_stats = input_data.metadata.get("mock_frame_stats", {})
            if mock_stats:
                self._from_mock_stats(result, mock_stats)
                context["source"] = "mock"
                context["lighting_normalized"] = True
                context["crop_mask_applied"] = True

        # Derive yellow/brown from channel ratios
        self._derive_color_features(result)

        return result, context

    # ================================================================
    # Real image loading
    # ================================================================

    def _load_real_image(self, result: PreprocessResult,
                         input_data: IPCameraEngineInput,
                         image_ref: str, image_bytes: Optional[bytes]) -> None:
        """Load frame via OpenCV and extract all stats."""
        try:
            if image_bytes:
                nparr = np.frombuffer(image_bytes, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            else:
                if not os.path.exists(image_ref):
                    raise FileNotFoundError(f"Frame not found: {image_ref}")
                img = cv2.imread(image_ref)

            if img is None:
                raise ValueError("cv2 decode returned None")

            h, w = img.shape[:2]
            result.width = w
            result.height = h

            # --- Apply ROI mask if provided ---
            roi_polygon = input_data.metadata.get("roi_polygon")
            if roi_polygon and len(roi_polygon) >= 3:
                img = self._apply_roi_mask(img, roi_polygon)

            # --- Full-frame channel ratios ---
            b_ch, g_ch, r_ch = cv2.split(img)
            sum_r = float(np.sum(r_ch))
            sum_g = float(np.sum(g_ch))
            sum_b = float(np.sum(b_ch))
            total = sum_r + sum_g + sum_b

            if total > 0:
                result.red_ratio = sum_r / total
                result.green_ratio = sum_g / total
                result.blue_ratio = sum_b / total

            # --- HSV for brightness and saturation ---
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            v_chan = hsv[:, :, 2]
            s_chan = hsv[:, :, 1]

            result.brightness_mean = float(np.mean(v_chan))
            result.brightness_std = float(np.std(v_chan))
            result.saturation_mean = float(np.mean(s_chan))
            result.overexposed_pct = float(np.sum(v_chan > 240) / (w * h)) * 100
            result.underexposed_pct = float(np.sum(v_chan < 15) / (w * h)) * 100

            # --- Blur via Laplacian variance ---
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            result.laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())

            # --- Crop / Soil / Sky segmentation ---
            self._segment_crop_soil_sky(result, img, hsv, gray, r_ch, g_ch, b_ch)

            # --- Per-region stats (crop region only) ---
            self._compute_crop_region_stats(result, img, hsv)

            # --- Histogram descriptor ---
            result.hsv_histogram = self._compute_histogram_descriptor(hsv)

            # --- Edge density ---
            edges = cv2.Canny(gray, 50, 150)
            result.edge_density = float(np.sum(edges > 0) / (w * h))

            # --- Per-tile Laplacian (for rain detection) ---
            result.tile_laplacian_values = self._compute_tile_laplacians(gray)

            # --- Quadrant brightness (for spatial uniformity) ---
            result.quadrant_brightness = self._compute_quadrant_brightness(v_chan)

            # --- Gray thumbnail for stale-frame SSIM ---
            result.gray_thumbnail_64 = cv2.resize(gray, (64, 64),
                                                    interpolation=cv2.INTER_AREA)

            # --- RGB tensor ---
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            result.image_rgb_uint8 = img_rgb.copy()
            result.resized_tensor = self._make_canonical_tensor(img_rgb)

            result.real_image_loaded = True

        except Exception as e:
            result.load_error = str(e)
            result.real_image_loaded = False

    # ================================================================
    # ROI masking
    # ================================================================

    def _apply_roi_mask(self, img: Any, roi_polygon: list) -> Any:
        """
        Apply an ROI polygon mask to the image.
        Pixels outside the polygon are zeroed.
        roi_polygon: list of [x, y] coordinate pairs.
        """
        mask = np.zeros(img.shape[:2], dtype=np.uint8)
        pts = np.array(roi_polygon, dtype=np.int32).reshape((-1, 1, 2))
        cv2.fillPoly(mask, [pts], 255)
        return cv2.bitwise_and(img, img, mask=mask)

    # ================================================================
    # Crop / Soil / Sky segmentation
    # ================================================================

    def _segment_crop_soil_sky(self, result: PreprocessResult,
                                img: Any, hsv: Any, gray: Any,
                                r_ch: Any, g_ch: Any, b_ch: Any) -> None:
        """
        HSV-based vegetation / soil / sky segmentation.
        Vegetation: H∈[25,90], S>40, V>30
        Sky: H∈[90,140], S<80, V>150
        Soil: remainder
        """
        h_chan = hsv[:, :, 0]
        s_chan = hsv[:, :, 1]
        v_chan = hsv[:, :, 2]
        total_pixels = float(img.shape[0] * img.shape[1])

        # Vegetation mask
        veg_mask = (
            (h_chan >= 25) & (h_chan <= 90) &
            (s_chan > 40) & (v_chan > 30)
        ).astype(np.uint8)
        # Morphological cleanup
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        veg_mask = cv2.morphologyEx(veg_mask, cv2.MORPH_OPEN, kernel)
        veg_mask = cv2.morphologyEx(veg_mask, cv2.MORPH_CLOSE, kernel)

        # Sky mask
        sky_mask = (
            (h_chan >= 90) & (h_chan <= 140) &
            (s_chan < 80) & (v_chan > 150)
        ).astype(np.uint8)

        # Fractions
        result.green_coverage_fraction = float(np.sum(veg_mask > 0) / total_pixels)
        result.sky_fraction = float(np.sum(sky_mask > 0) / total_pixels)
        result.soil_fraction = max(0.0, 1.0 - result.green_coverage_fraction - result.sky_fraction)

        # Store the vegetation mask
        result.crop_mask = (veg_mask * 255).astype(np.uint8)

    # ================================================================
    # Per-region stats
    # ================================================================

    def _compute_crop_region_stats(self, result: PreprocessResult,
                                    img: Any, hsv: Any) -> None:
        """Compute stats only within the crop (vegetation) mask region."""
        if result.crop_mask is None:
            return

        mask_bool = result.crop_mask > 0
        n_crop_px = int(np.sum(mask_bool))
        if n_crop_px < 100:
            # Too few crop pixels to compute meaningful stats
            return

        b_ch, g_ch, r_ch = cv2.split(img)
        crop_r = r_ch[mask_bool].astype(float)
        crop_g = g_ch[mask_bool].astype(float)
        crop_b = b_ch[mask_bool].astype(float)
        crop_total = np.sum(crop_r) + np.sum(crop_g) + np.sum(crop_b)

        if crop_total > 0:
            result.crop_region_green_ratio = float(np.sum(crop_g) / crop_total)

        crop_v = hsv[:, :, 2][mask_bool].astype(float)
        crop_s = hsv[:, :, 1][mask_bool].astype(float)
        result.crop_region_brightness = float(np.mean(crop_v))
        result.crop_region_saturation = float(np.mean(crop_s))

    # ================================================================
    # Histogram descriptor
    # ================================================================

    def _compute_histogram_descriptor(self, hsv: Any) -> Any:
        """
        Compute a normalized 3-channel HSV histogram.
        H: 32 bins, S: 16 bins, V: 16 bins -> total 8192 bin descriptor.
        """
        hist = cv2.calcHist(
            [hsv], [0, 1, 2], None,
            [32, 16, 16],
            [0, 180, 0, 256, 0, 256]
        )
        cv2.normalize(hist, hist, alpha=1.0, norm_type=cv2.NORM_L1)
        return hist

    # ================================================================
    # Per-tile Laplacian (rain-on-lens detection)
    # ================================================================

    def _compute_tile_laplacians(self, gray: Any, grid_size: int = 8) -> List[float]:
        """
        Divide frame into grid_size×grid_size tiles and compute
        Laplacian variance per tile. Rain droplets create localized
        high-frequency bokeh in some tiles but not others.
        """
        h, w = gray.shape
        tile_h = h // grid_size
        tile_w = w // grid_size
        values = []
        for row in range(grid_size):
            for col in range(grid_size):
                tile = gray[row * tile_h:(row + 1) * tile_h,
                            col * tile_w:(col + 1) * tile_w]
                if tile.size > 0:
                    lap_var = float(cv2.Laplacian(tile, cv2.CV_64F).var())
                    values.append(lap_var)
        return values

    # ================================================================
    # Quadrant brightness (spatial uniformity)
    # ================================================================

    def _compute_quadrant_brightness(self, v_chan: Any) -> List[float]:
        """
        Compute mean brightness in 4 quadrants.
        Large disparity indicates partial obstruction or lens dirt.
        """
        h, w = v_chan.shape
        mid_h, mid_w = h // 2, w // 2
        return [
            float(np.mean(v_chan[:mid_h, :mid_w])),       # top-left
            float(np.mean(v_chan[:mid_h, mid_w:])),        # top-right
            float(np.mean(v_chan[mid_h:, :mid_w])),        # bottom-left
            float(np.mean(v_chan[mid_h:, mid_w:])),         # bottom-right
        ]

    # ================================================================
    # Canonical tensor
    # ================================================================

    def _make_canonical_tensor(self, img_rgb: Any) -> Any:
        """Resize to 224x224, convert to float32 NCHW [0,1]."""
        resized = cv2.resize(img_rgb, (224, 224), interpolation=cv2.INTER_LINEAR)
        tensor = resized.astype(np.float32) / 255.0
        tensor = np.transpose(tensor, (2, 0, 1))  # HWC -> CHW
        return np.expand_dims(tensor, axis=0)       # add N dim

    # ================================================================
    # Mock stats fallback
    # ================================================================

    def _from_mock_stats(self, result: PreprocessResult, stats: Dict) -> None:
        """Populate PreprocessResult from mock stats dict (test path)."""
        result.brightness_mean = stats.get("mean_brightness", 120.0)
        result.brightness_std = stats.get("brightness_std", 30.0)
        result.saturation_mean = stats.get("saturation_mean", 100.0)
        result.laplacian_var = stats.get("sharpness", 50.0)
        result.green_ratio = stats.get("green_fraction", 0.33)
        result.green_coverage_fraction = stats.get("green_fraction", 0.33)
        result.overexposed_pct = stats.get("overexposed_pct", 0.0)
        result.underexposed_pct = stats.get("underexposed_pct", 0.0)
        result.shift_x = stats.get("shift_x", 0.0)
        result.shift_y = stats.get("shift_y", 0.0)
        result.phenology_stage_est = stats.get("phenology_stage_est", 2.0)
        result.soil_fraction = stats.get("soil_fraction", 0.0)
        result.sky_fraction = stats.get("sky_fraction", 0.0)
        result.edge_density = stats.get("edge_density", 0.05)
        result.crop_region_green_ratio = stats.get("green_fraction", 0.33)
        result.crop_region_brightness = stats.get("mean_brightness", 120.0)
        result.crop_region_saturation = stats.get("saturation_mean", 100.0)

        # Infer yellow from explicit yellow_fraction if provided
        yellow_frac = stats.get("yellow_fraction", 0.0)
        if yellow_frac > 0:
            result.yellow_ratio = yellow_frac

    # ================================================================
    # Color feature derivation
    # ================================================================

    def _derive_color_features(self, result: PreprocessResult) -> None:
        """Derive yellow and brown ratios from channel ratios."""
        r = result.red_ratio
        g = result.green_ratio
        b = result.blue_ratio

        # Yellow: R and G both exceed B
        if result.yellow_ratio == 0.0:
            if r > b and g > b and b < 0.30:
                yellow_strength = (r + g - 2 * b) / max(r + g + b, 0.01)
                result.yellow_ratio = min(1.0, yellow_strength)

        # Brown: R dominates both G and B
        rg_gap = r - g
        rb_gap = r - b
        has_earth_tone = 40 < result.brightness_mean < 200
        if rg_gap > 0.02 and rb_gap > 0.02 and has_earth_tone:
            dominance = (r - max(g, b)) / max(r + g + b, 0.01)
            result.brown_ratio = min(1.0, dominance * 4.0)
