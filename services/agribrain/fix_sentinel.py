"""
Surgical fixes for eo/sentinel.py:
1. Replace emoji in print() statements that crash cp1252 encoding
2. Fix duplicate except block in fetch_soil_moisture_proxy
3. Fix bands[0] IndexError in Stats API parsers  
4. Lower water balance archive timeout 15->8s
"""
import re, sys, subprocess

with open("eo/sentinel.py", "r", encoding="utf-8") as f:
    text = f.read()

original = text

# ---------------------------------------------------------------------------
# 1. Emoji replacements (only in Python string literals / print statements)
#    Safe: Arabic stays (it's in data dicts, not print paths that crash cp1252)
#    Problem chars: U+26A0 ⚠, U+FE0F (variation selector), U+274C ❌, U+1F511 🔑
# ---------------------------------------------------------------------------
emoji_map = {
    "\u26a0\ufe0f": "[WARN]",   # ⚠️
    "\u26a0":       "[WARN]",   # ⚠
    "\ufe0f":       "",          # variation selector (standalone)
    "\u274c":       "[ERROR]",  # ❌
    "\U0001f511":   "[KEY]",    # 🔑
    "\u2714":       "[OK]",     # ✔
    "\u2705":       "[OK]",     # ✅
    "\U0001f6f0":   "[SAT]",   # 🛰
    "\U0001f504":   "[SYNC]",  # 🔄
    "\U0001f50c":   "[PLUG]",  # 🔌
}
for emoji, replacement in emoji_map.items():
    if emoji in text:
        count = text.count(emoji)
        text = text.replace(emoji, replacement)
        print(f"Replaced {count}x U+{ord(emoji[0]):04X} -> '{replacement}'")

# ---------------------------------------------------------------------------
# 2. Fix duplicate except block in fetch_soil_moisture_proxy
# ---------------------------------------------------------------------------
# Pattern to find and remove the duplicate block (both CRLF and LF)
for nl in ["\r\n", "\n"]:
    dup = (
        f"    except Exception as e:{nl}"
        f'        print(f"SAR fetch error: {{e}}"){nl}'
        f"    {nl}"
        f"    except Exception as e:{nl}"
        f'        print(f"SAR fetch error: {{e}}"){nl}'
        f"    {nl}"
        f"    return None"
    )
    fixed = (
        f"    except Exception as e:{nl}"
        f'        print(f"SAR fetch error: {{e}}"){nl}'
        f"    return None"
    )
    if dup in text:
        text = text.replace(dup, fixed)
        print("Fixed: duplicate except in fetch_soil_moisture_proxy")
        break
else:
    print("WARNING: Could not find duplicate except pattern")

# ---------------------------------------------------------------------------
# 3. Fix bands[0] IndexError in fetch_soil_moisture_proxy
#    Replace the three output extraction lines (around line 739-741 original)
# ---------------------------------------------------------------------------
for nl in ["\r\n", "\n"]:
    old = (
        f'        vv = outputs.get("vv", {{}}).get("bands", [{{}}])[0].get("stats", {{}}).get("mean"){nl}'
        f'        vh = outputs.get("vh", {{}}).get("bands", [{{}}])[0].get("stats", {{}}).get("mean"){nl}'
        f'        ratio = outputs.get("ratio", {{}}).get("bands", [{{}}])[0].get("stats", {{}}).get("mean")'
    )
    new = (
        f'        vv_bands = outputs.get("vv", {{}}).get("bands") or [{{}}{nl}'
        f'        vh_bands = outputs.get("vh", {{}}).get("bands") or [{{}}{nl}'
        f'        ratio_bands = outputs.get("ratio", {{}}).get("bands") or [{{}}{nl}'
        f'        vv = vv_bands[0].get("stats", {{}}).get("mean") if vv_bands else None{nl}'
        f'        vh = vh_bands[0].get("stats", {{}}).get("mean") if vh_bands else None{nl}'
        f'        ratio = ratio_bands[0].get("stats", {{}}).get("mean") if ratio_bands else None'
    )
    if old in text:
        text = text.replace(old, new)
        print("Fixed: SAR bands[0] IndexError")
        break
else:
    print("WARNING: SAR pattern not found - trying manual line search")

# ---------------------------------------------------------------------------
# 4. Fix bands[0] IndexError in fetch_vegetation_indices
# ---------------------------------------------------------------------------
for nl in ["\r\n", "\n"]:
    old = (
        f'            "ndvi": outputs.get("ndvi", {{}}).get("bands", [{{}}])[0].get("stats", {{}}).get("mean"),{nl}'
        f'            "evi": outputs.get("evi", {{}}).get("bands", [{{}}])[0].get("stats", {{}}).get("mean"),{nl}'
        f'            "ndwi": outputs.get("ndwi", {{}}).get("bands", [{{}}])[0].get("stats", {{}}).get("mean"),{nl}'
        f'            "ndmi": outputs.get("ndmi", {{}}).get("bands", [{{}}])[0].get("stats", {{}}).get("mean"),'
    )
    new = (
        f'            "ndvi": (outputs.get("ndvi", {{}}).get("bands") or [{{}}])[0].get("stats", {{}}).get("mean"),{nl}'
        f'            "evi": (outputs.get("evi", {{}}).get("bands") or [{{}}])[0].get("stats", {{}}).get("mean"),{nl}'
        f'            "ndwi": (outputs.get("ndwi", {{}}).get("bands") or [{{}}])[0].get("stats", {{}}).get("mean"),{nl}'
        f'            "ndmi": (outputs.get("ndmi", {{}}).get("bands") or [{{}}])[0].get("stats", {{}}).get("mean"),'
    )
    if old in text:
        text = text.replace(old, new)
        print("Fixed: vegetation indices bands[0] IndexError")
        break
else:
    print("WARNING: veg indices pattern not found")

# ---------------------------------------------------------------------------
# 5. Water balance archive timeout 15 -> 8s
# ---------------------------------------------------------------------------
old_timeout = 'hist_res = requests.get(OPEN_METEO_ARCHIVE_URL, params=history_params, timeout=15)'
new_timeout = 'hist_res = requests.get(OPEN_METEO_ARCHIVE_URL, params=history_params, timeout=8)'
if old_timeout in text:
    text = text.replace(old_timeout, new_timeout)
    print("Fixed: water balance archive timeout 15->8s")
else:
    print("WARNING: archive timeout line not found")

# ---------------------------------------------------------------------------
# Write and verify syntax
# ---------------------------------------------------------------------------
with open("eo/sentinel.py", "w", encoding="utf-8") as f:
    f.write(text)
print(f"\nFile written: {len(original)} -> {len(text)} bytes")

r = subprocess.run(
    [sys.executable, "-c", "import ast; ast.parse(open('eo/sentinel.py', encoding='utf-8').read())"],
    capture_output=True, text=True
)
if r.returncode == 0:
    print("Syntax: OK")
else:
    print(f"SYNTAX ERROR:\n{r.stderr}")
