import os

root_dir = "c:/Users/E-C/Desktop/agriwise/services"

def is_python_dir(d):
    # Check if there are .py files inside (recursively or directly)
    for root, dirs, files in os.walk(d):
        if any(f.endswith(".py") for f in files):
            return True
    return False

for root, dirs, files in os.walk(root_dir):
    if "__pycache__" in root:
        continue
    # We only add __init__.py if there's python files in this directory
    has_py = any(f.endswith(".py") and f != "__init__.py" for f in files)
    
    # Or if it's explicitly mentioned by the user
    # services/agribrain/layer0/perception/*/benchmark/
    
    # Just add to all dirs that contain any .py file or are subdirectories of a package
    if has_py or "benchmark" in root or "tests" in root:
        init_path = os.path.join(root, "__init__.py")
        if not os.path.exists(init_path):
            with open(init_path, "w") as f:
                pass
            print(f"Created {init_path}")

print("Done")
