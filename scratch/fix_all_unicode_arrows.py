import os
import glob

all_files = glob.glob("c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/**/*.py", recursive=True)
for file in all_files:
    try:
        with open(file, "r", encoding="utf-8") as f:
            content = f.read()
            
        modified = False
        if "\u2192" in content:
            content = content.replace("\u2192", "->")
            modified = True
        if "→" in content:
            content = content.replace("→", "->")
            modified = True
            
        if modified:
            with open(file, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Fixed {file}")
    except Exception as e:
        pass
print("Done fixing all unicode arrows!")
