import os
import sys

# Add directories to path
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve() / "services" / "agribrain"))
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

os.environ["ASMAE_TEST_OVERRIDE"] = "true"
os.environ["ASMAE_ENABLED"] = "true"
os.environ["ASMAE_DIAGNOSTIC_SHADOW_RUN_ENABLED"] = "true"

from layer05_asmae.runner import ASMAERunner
from layer10_sire.l10_frontend_bridge import build_input_from_context
from layer10_sire.runner import run_layer10_sire

ctx_normal = {
    "raster_composites": {
        "NDVI": {
            "values": [[0.5 if (r + c) % 2 == 0 else 0.6 for c in range(8)] for r in range(8)],
            "grid_spec": {"crs": "EPSG:4326"}
        }
    },
    "geometry_hash": "geom_normal",
    "polygon_geojson": {"type": "Polygon", "coordinates": [[[0,0], [0,1], [1,1], [0,0]]]},
    "is_background_run": True
}
runner = ASMAERunner()
res_normal = runner.execute("unregistered_plot_uuid_normal", "run_normal", ctx_normal, mode="shadow")
l10_input = build_input_from_context({"plotId": "GATE_V924_BC9", "lat": 36.7, "lng": 3.0, "crop": "wheat", "sourcePolicy": "hybrid"})
l10_input.plot_id = "plot_normal"
l10_input.source_policy = "hybrid"

class MockContextPackage:
    def __init__(self, asmae_output):
        self.asmae_output = asmae_output
        self.raster_composites = {
            "NDVI": [[0.5 if (r + c) % 2 == 0 else 0.6 for c in range(8)] for r in range(8)]
        }
l10_input.field_tensor._context_package = MockContextPackage(res_normal)

# Inspect generate_asmae_surfaces directly
from layer10_sire.adapters.l1_adapter import adapt_l1
from layer10_sire.surfaces.asmae import generate_asmae_surfaces, generate_asmae_aliases, asmae_surface_pixel_visual_eligible

H, W = 8, 8
l1_data = adapt_l1(l10_input.field_tensor, H, W)
print("l1_data.raster_maps keys:", list(l1_data.raster_maps.keys()))
print("l1_data.real_asmae_evidence:", l1_data.real_asmae_evidence)

surfaces = generate_asmae_surfaces(l10_input, H, W, l1_data=l1_data)
print("generate_asmae_surfaces length:", len(surfaces))
print("surface types:", [s.semantic_type for s in surfaces])

display_grid_spec = {
    "width": 32,
    "height": 32,
    "bounds": (3.0, 36.7 - 8 * 0.00009, 3.0 + 8 * 0.00009, 36.7),
}

for s in surfaces:
    if "VIGOR" in str(s.semantic_type):
        print("s.provenance of VIGOR:", s.provenance)
        print("pixel eligible check:", asmae_surface_pixel_visual_eligible(s, output_grid_spec=display_grid_spec))

print("running generate_asmae_aliases...")
aliases = generate_asmae_aliases(H, W, surfaces, l10_input, grid_spec_dict=display_grid_spec)
print("generated aliases:", [a.semantic_type for a in aliases])
