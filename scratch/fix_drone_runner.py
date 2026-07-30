import os

fp_runner = "c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/perception/drone_rgb/benchmark/run_benchmark.py"

with open(fp_runner, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("'\u2500' * 72", "'-' * 72")
content = content.replace("'\u2500' * 80", "'-' * 80")
content = content.replace("'\u2500' * 30", "'-' * 30")
content = content.replace("'\u2500' * 18", "'-' * 18")
content = content.replace("'\u2500' * 6", "'-' * 6")
content = content.replace("'\u2500' * 5", "'-' * 5")
content = content.replace("'\u2500' * 4", "'-' * 4")
content = content.replace("'\u2500'", "'-'")
content = content.replace("─", "-")

# Also check for emoji
content = content.replace("⚠️", "[WARN]")
content = content.replace("✅", "[PASS]")
content = content.replace("❌", "[FAIL]")

with open(fp_runner, 'w', encoding='utf-8') as f:
    f.write(content)
