
from enum import Enum
from typing import Callable, Any, List, Dict
from dataclasses import dataclass

# Layer Runners
from services.agribrain.layer1_fusion.runner import run_layer1_fusion
from services.agribrain.layer2_veg_int.runner import run_layer2_veg
from services.agribrain.layer3_decision.runner import run_layer3_decision
from services.agribrain.layer4_nutrients.runner import run_layer4_nutrients
from services.agribrain.layer5_bio.runner import run_layer5_bio
from services.agribrain.layer6_exec.runner import run_layer6_exec
from services.agribrain.layer7_planning.runner import run as run_layer7_planning

class LayerId(str, Enum):
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"
    L5 = "L5"
    L6 = "L6"
    L7 = "L7"

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
        runner=run_layer2_veg,
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
        version="5.0.0",
        runner=run_layer5_bio,
        depends_on=[LayerId.L1, LayerId.L2],
        required=False
    ),
    LayerId.L6: LayerSpec(
        id=LayerId.L6,
        name="Execution",
        version="6.0.0",
        runner=run_layer6_exec,
        depends_on=[LayerId.L3], # Technically consumes L4/L5 too if present
        required=True
    ),
    LayerId.L7: LayerSpec(
        id=LayerId.L7,
        name="SeasonPlanning",
        version="7.0.0",
        runner=run_layer7_planning,
        depends_on=[LayerId.L1],
        required=False
    )
}

def get_layer_versions() -> Dict[str, str]:
    return {k.value: v.version for k, v in LAYER_REGISTRY.items()}
