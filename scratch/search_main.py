import sys
sys.stdout.reconfigure(encoding='utf-8')

with open(r'c:\Users\E-C\Desktop\agriwise\services\agribrain\layer1_fusion\zone_engine.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print("Searching zone_engine.py...")
for idx, line in enumerate(lines):
    if 'def ' in line or 'zones =' in line or 'zone_' in line:
        print(f"{idx+1}: {line.strip()}")
