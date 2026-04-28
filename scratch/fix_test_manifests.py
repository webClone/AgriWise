import os
import glob

for filename in glob.glob("c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/**/test_*.py", recursive=True):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if 'entry["file"]' in content or "entry.get('file')" in content or 'entry.get("file")' in content:
            content = content.replace('entry["file"]', 'entry.get("filename", entry.get("file", ""))')
            content = content.replace("entry.get('file')", 'entry.get("filename", "")')
            content = content.replace('entry.get("file")', 'entry.get("filename", "")')
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Fixed {filename}")
    except Exception as e:
        print(e)
