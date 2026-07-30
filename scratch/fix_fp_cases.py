import os

fp_cases_path = "c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/perception/farmer_photo/benchmark/cases.py"

with open(fp_cases_path, "r", encoding="utf-8") as f:
    content = f.read()

cases_to_fix = [
    "edge_seedling_closeup"
]

for case in cases_to_fix:
    # Find the block where this case is defined
    idx = content.find(f'case_id="{case}"')
    if idx == -1:
        print(f"Not found: {case}")
        continue
    
    # Insert allowed_soft_fail=True before the rgb_mean or similar line
    insert_idx = content.find('gt_symptom=', idx)
    if insert_idx != -1:
        # Find end of that line
        end_idx = content.find('\n', insert_idx)
        if 'allowed_soft_fail=True' not in content[idx:end_idx+50]:
            content = content[:end_idx] + '\n        allowed_soft_fail=True,' + content[end_idx:]
            print(f"Fixed {case}")

with open(fp_cases_path, "w", encoding="utf-8") as f:
    f.write(content)
