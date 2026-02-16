
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.agribrain.layer1_fusion.schema import FusionOutput, FieldTensor

try:
    print("Testing FusionOutput instantiation...")
    tensor = FieldTensor(plot_id="p1", run_id="r1")
    out = FusionOutput(
        tensor=tensor,
        evidence_summary=[],
        validation_report={},
        logs=[{"event": "test"}]
    )
    print("✅ Success!")
    print(out.logs)
except Exception as e:
    print(f"❌ Failed: {e}")
    import traceback
    traceback.print_exc()
