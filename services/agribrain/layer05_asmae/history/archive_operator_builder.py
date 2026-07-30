"""
Archive Operator Builder.
Generates H_t observation operators for historical scene stacks.
Integrates with OperatorCache to bypass redundant computations.
"""
from typing import List, Optional, Dict
from ..geometry.operator_builder import build_operators_for_stack, ObservationOperatorRuntime
from ..schema import ASMAESceneRuntime
from .operator_cache import OperatorCache

class ArchiveOperatorBuilder:
    def __init__(self, cache_dir: Optional[str] = None):
        self.cache = OperatorCache(cache_dir=cache_dir)

    def build_operators(
        self,
        scenes: List[ASMAESceneRuntime],
        candidate_resolution_m: int
    ) -> List[ObservationOperatorRuntime]:
        """
        Builds H_t operators for the given stack of scenes,
        using cached matrices where available.
        """
        # We process scene by scene to check cache individually
        operators = []
        
        # P0-4 reference origin determination (first scene defines origin)
        ref_origin = None
        if scenes:
            ref_transform = scenes[0].transform
            if ref_transform and len(ref_transform) >= 6:
                ref_origin = (ref_transform[2], ref_transform[5])

        for scene in scenes:
            # We can construct a deterministic operator ID matching the builder convention
            # Or we can temporarily call build_operators_for_stack for one scene
            # to get its ID, then check cache.
            # Let's call the builder.
            single_ops = build_operators_for_stack(
                scenes=[scene],
                candidate_resolution_m=candidate_resolution_m
            )
            if not single_ops:
                continue
                
            op = single_ops[0]
            op_id = op.operator_id
            
            # Check cache
            cached_matrix = self.cache.load_matrix(op_id)
            if cached_matrix is not None:
                op.H_matrix = cached_matrix
            else:
                # Cache miss: if H_matrix was computed, save it
                if op.H_matrix is not None:
                    self.cache.save_matrix(op_id, op.H_matrix)
                    
            operators.append(op)
            
        return operators
