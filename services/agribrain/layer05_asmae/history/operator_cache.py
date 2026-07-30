"""
Observation Operator Matrix Cache.
Saves and loads Scipy CSR sparse matrices safely to NPZ files,
strictly enforcing allow_pickle=False and executing atomic writes.
"""
import os
import tempfile
import numpy as np
from scipy import sparse as sp
from typing import Optional

class OperatorCache:
    def __init__(self, cache_dir: Optional[str] = None):
        if not cache_dir:
            base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            cache_dir = os.path.join(base, "data", "operator_cache")
        self.cache_dir = cache_dir

    def get_cache_path(self, operator_id: str) -> str:
        return os.path.join(self.cache_dir, f"{operator_id}.npz")

    def has_operator(self, operator_id: str) -> bool:
        return os.path.exists(self.get_cache_path(operator_id))

    def load_matrix(self, operator_id: str) -> Optional[sp.csr_matrix]:
        """Loads a CSR matrix from NPZ, enforcing allow_pickle=False."""
        file_path = self.get_cache_path(operator_id)
        if not os.path.exists(file_path):
            return None
        try:
            with np.load(file_path, allow_pickle=False) as loader:
                data = loader["data"]
                indices = loader["indices"]
                indptr = loader["indptr"]
                shape = tuple(loader["shape"])
                return sp.csr_matrix((data, indices, indptr), shape=shape)
        except Exception:
            return None

    def save_matrix(self, operator_id: str, matrix: sp.csr_matrix) -> None:
        """Saves a CSR matrix to NPZ atomically, enforcing allow_pickle=False."""
        os.makedirs(self.cache_dir, exist_ok=True)
        file_path = self.get_cache_path(operator_id)
        
        fd, temp_path = tempfile.mkstemp(dir=self.cache_dir, suffix=".npz")
        os.close(fd)
        
        try:
            # Enforce allow_pickle=False
            np.savez(
                temp_path,
                data=matrix.data,
                indices=matrix.indices,
                indptr=matrix.indptr,
                shape=np.array(matrix.shape),
                allow_pickle=False
            )
            os.replace(temp_path, file_path)
        except Exception as e:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            raise e
