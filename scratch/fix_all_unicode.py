import os
import glob

for filename in glob.glob("c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/**/*.py", recursive=True):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
            
        changed = False
        for char in ['✅', '❌', '✓', '✗', '⚠️', '📈', '🚀', '🟢', '🔴', '🟡']:
            if char in content:
                content = content.replace(char, '')
                changed = True
                
        if changed:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Fixed {filename}")
    except Exception as e:
        pass
