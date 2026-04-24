import os
with open(r"C:\Users\E-C\.gemini\antigravity\brain\85959307-9048-4c0c-91e7-964a6624409c\.system_generated\logs\overview.txt", 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if "brown_ratio" in line or "dominates" in line or "saturation" in line:
        print(f"L{i}: {line.strip()[:100]}")
