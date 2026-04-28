import os
import glob

all_tests = glob.glob("c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/**/*.py", recursive=True)
for file in all_tests:
    try:
        with open(file, "r", encoding="utf-8") as f:
            content = f.read()
            
        modified = False
        if 'entry.get("filename", entry.get("file", ""))' in content:
            content = content.replace('entry.get("filename", entry.get("file", ""))', 'entry.get("local_path", entry.get("filename", entry.get("file", "")))')
            modified = True
            
        if 'entry.get("filename", "")' in content:
            content = content.replace('entry.get("filename", "")', 'entry.get("local_path", entry.get("filename", ""))')
            modified = True
            
        if modified:
            with open(file, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Fixed {file}")
    except Exception as e:
        pass
print("Done fixing test paths!")
