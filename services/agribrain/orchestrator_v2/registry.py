
from enum import Enum
from typing import Callable, Any, List, Dict
from dataclasses import dataclass
import importlib


def _lazy_runner(module_name: str, function_name: str) -> Callable[..., Any]:
    """Resolve a layer runner only when that layer is actually executed.

    Registry import must remain a lightweight package-contract operation.  The
    previous eager imports bootstrapped every layer and made orchestrator
    importability depend on the legacy ``services/agribrain`` PYTHONPATH.
    """
    target: Callable[..., Any] | None = None

    def invoke(*args: Any, **kwargs: Any) -> Any:
        nonlocal target
        if target is None:
            module = importlib.import_module(module_name)
            target = getattr(module, function_name)
        return target(*args, **kwargs)

    invoke.__name__ = function_name
    invoke.__module__ = module_name
    return invoke


# Layer runners use the one installed backend namespace and load on demand.
run_layer1_fusion = _lazy_runner("services.agribrain.layer1_fusion.runner", "run_layer1_fusion")
run_layer2_composite = _lazy_runner("services.agribrain.layer2_intelligence.composite_runner", "run_layer2_composite")
run_layer3_decision = _lazy_runner("services.agribrain.layer3_decision.runner", "run_layer3_decision")
run_layer4_nutrients = _lazy_runner("services.agribrain.layer4_nutrients.runner", "run_layer4_nutrients")
run_layer5_bio = _lazy_runner("services.agribrain.layer5_bio.runner", "run_layer5_bio")
run_layer6_exec = _lazy_runner("services.agribrain.layer6_exec.runner", "run_layer6_exec")
run_layer7_planning = _lazy_runner("services.agribrain.layer7_planning.runner", "run")
run_layer8 = _lazy_runner("services.agribrain.layer8_prescriptive.runner", "run_layer8")
run_layer10_sire = _lazy_runner("services.agribrain.layer10_sire.runner", "run_layer10_sire")
run_layer9 = _lazy_runner("services.agribrain.layer9_interface.runner", "run_layer9")

class LayerId(str, Enum):
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"
    L5 = "L5"
    L6 = "L6"
    L7 = "L7"
    L8 = "L8"
    L10 = "L10"
    L9 = "L9"

@dataclass
class LayerSpec:
    id: LayerId
    name: str
    version: str
    runner: Callable
    depends_on: List[LayerId]
    required: bool = True # If False, failure is non-fatal (DEGRADED)

# Central Registry
LAYER_REGISTRY: Dict[LayerId, LayerSpec] = {
    LayerId.L1: LayerSpec(
        id=LayerId.L1,
        name="Fusion",
        version="1.0.0",
        runner=run_layer1_fusion,
        depends_on=[]
    ),
    LayerId.L2: LayerSpec(
        id=LayerId.L2,
        name="Vegetation",
        version="2.0.0",
        runner=run_layer2_composite,
        depends_on=[LayerId.L1]
    ),
    LayerId.L3: LayerSpec(
        id=LayerId.L3,
        name="Decision",
        version="3.0.0",
        runner=run_layer3_decision,
        depends_on=[LayerId.L2]
    ),
    LayerId.L4: LayerSpec(
        id=LayerId.L4,
        name="Nutrients",
        version="4.0.0",
        runner=run_layer4_nutrients,
        depends_on=[LayerId.L2, LayerId.L3],
        required=False 
    ),
    LayerId.L5: LayerSpec(
        id=LayerId.L5,
        name="BioThreat",
        version="6.0.0",
        runner=run_layer5_bio,
        depends_on=[LayerId.L1, LayerId.L2, LayerId.L3, LayerId.L4],
        required=False
    ),
    LayerId.L6: LayerSpec(
        id=LayerId.L6,
        name="Execution",
        version="7.0.0",
        runner=run_layer6_exec,
        depends_on=[LayerId.L1, LayerId.L2, LayerId.L3, LayerId.L4, LayerId.L5],
        required=True
    ),
    LayerId.L7: LayerSpec(
        id=LayerId.L7,
        name="SeasonPlanning",
        version="7.0.0",
        runner=run_layer7_planning,
        depends_on=[LayerId.L1, LayerId.L2, LayerId.L3, LayerId.L4, LayerId.L5, LayerId.L6],
        required=False
    ),
    LayerId.L8: LayerSpec(
        id=LayerId.L8,
        name="Prescriptive",
        version="8.1.0",
        runner=run_layer8,
        depends_on=[LayerId.L3, LayerId.L4, LayerId.L5, LayerId.L6, LayerId.L7],
        required=False
    ),
    LayerId.L10: LayerSpec(
        id=LayerId.L10,
        name="SIRE",
        version="10.5.0",
        runner=run_layer10_sire,
        depends_on=[LayerId.L1, LayerId.L2, LayerId.L3, LayerId.L4, LayerId.L5, LayerId.L7, LayerId.L8],
        required=False
    ),
    LayerId.L9: LayerSpec(
        id=LayerId.L9,
        name="Interface",
        version="9.0.0",
        runner=run_layer9,
        depends_on=[LayerId.L8],
        required=False
    ),
}

def get_layer_versions() -> Dict[str, str]:
    return {k.value: v.version for k, v in LAYER_REGISTRY.items()}
