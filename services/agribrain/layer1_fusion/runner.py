
from typing import Optional
from services.agribrain.layer1_fusion.data_fusion import fusion_engine
from services.agribrain.layer1_fusion.schema import FieldTensor

def run_layer1_fusion(
    plot_id: str,
    lat: float,
    lng: float,
    start_date: str,
    end_date: str
) -> FieldTensor:
    """
    Standard Entry Point for Layer 1.
    Returns a FieldTensor populated with fused data.
    """
    output = fusion_engine.fuse_data(
        plot_id=plot_id,
        lat=lat,
        lng=lng,
        start_date=start_date,
        end_date=end_date
    )
    return output.tensor
