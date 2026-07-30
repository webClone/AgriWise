import numpy as np

def safe_np_load(file, fix_imports=True, encoding='ASCII'):
    """
    Safely load a numpy .npz or .npy file with allow_pickle=False.
    If the loading fails (e.g. because of object arrays / pickle usage),
    it raises a ValueError to prevent arbitrary code execution.
    """
    return np.load(file, allow_pickle=False, fix_imports=fix_imports, encoding=encoding)
