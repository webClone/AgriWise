import sys
import os

runner_path = "c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/perception/farmer_photo/benchmark/run_benchmark.py"

with open(runner_path, "r", encoding="utf-8") as f:
    content = f.read()

# Make sure sys is imported
if "import sys" not in content:
    content = content.replace("import os", "import os\nimport sys")

# Update all_ok and critical_failures check
if "critical_failures" not in content:
    content = content.replace("return results", """    critical_failures = 0
    for r in results:
        c = r.case
        scene_ok = r.scene_correct
        organ_ok = r.organ_correct
        symp_ok = r.symptom_correct
        bnd_ok = r.boundary_correct
        sev_ok = r.severity_error <= 0.20
        all_ok = scene_ok and organ_ok and symp_ok and bnd_ok and sev_ok
        if not all_ok and getattr(c, 'critical_case', True) and not getattr(c, 'allowed_soft_fail', False):
            critical_failures += 1

    return results, critical_failures""")

# Update __main__ block
if "critical_failures > 0" not in content:
    content = content.replace('run_benchmark(verbose=True)', '''results, critical_failures = run_benchmark(verbose=True)
    if critical_failures > 0:
        print(f"\\n[!] FAILED: {critical_failures} critical cases failed.")
        sys.exit(1)
    else:
        print("\\n[+] PASSED: All critical cases succeeded.")
        sys.exit(0)''')

with open(runner_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Updated farmer photo runner")
