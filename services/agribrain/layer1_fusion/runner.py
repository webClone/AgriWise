
from typing import Optional
from services.agribrain.layer1_fusion.data_fusion import fusion_engine
from services.agribrain.layer1_fusion.schema import FieldTensor

from services.agribrain.orchestrator_v2.schema import OrchestratorInput

def run_layer1_fusion(inputs: OrchestratorInput) -> FieldTensor:
    """
    Standard Entry Point for Layer 1.
    """
    # Extract params from V2 Input
    plot_id = inputs.plot_id
    lat = float(inputs.operational_context.get("lat", 0.0))
    lng = float(inputs.operational_context.get("lng", 0.0))
    polygon_coords = inputs.operational_context.get("polygon_coords")
    start_date = inputs.date_range.get("start", "")
    end_date = inputs.date_range.get("end", "")
    user_evidence = inputs.operational_context.get("user_evidence", [])
    
    output = fusion_engine.fuse_data(
        plot_id=plot_id,
        lat=lat,
        lng=lng,
        start_date=start_date,
        end_date=end_date,
        polygon_coords=polygon_coords,
        user_evidence=user_evidence
    )

    # Fix A: Propagate raster composites + observation products onto the tensor
    # so downstream layers (especially L10) can access real pixel grids.
    tensor = output.tensor
    if output.raster_composites:
        tensor.raster_composites = output.raster_composites
    if output.observation_products:
        tensor.observation_products = output.observation_products
    return tensor

