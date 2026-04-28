import os
import glob

for filename in glob.glob("c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/**/*.py", recursive=True):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if '✅' in content or '❌' in content or '✓' in content or '✗' in content:
            content = content.replace('✅', '[PASS]')
            content = content.replace('❌', '[FAIL]')
            content = content.replace('✓', 'PASS')
            content = content.replace('✗', 'FAIL')
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Fixed {filename}")
    except Exception as e:
        print(f"Error on {filename}: {e}")
