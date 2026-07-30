import os
import glob

# For drone tests
drone_tests = glob.glob("c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/perception/drone_rgb/**/*.py", recursive=True)
for file in drone_tests:
    with open(file, "r", encoding="utf-8") as f:
        content = f.read()
    if 'entry.get("filename", entry.get("file", ""))' in content or 'entry.get("filename", "")' in content:
        content = content.replace('os.path.join(os.path.dirname(__file__), entry.get("filename", entry.get("file", "")))', 
                                  'os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "common", "fixtures", "drone", entry.get("filename", entry.get("file", "")))')
        content = content.replace('os.path.join(os.path.dirname(__file__), entry.get("filename", ""))', 
                                  'os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "common", "fixtures", "drone", entry.get("filename", ""))')
        with open(file, "w", encoding="utf-8") as f:
            f.write(content)

# For satellite tests
sat_tests = glob.glob("c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/perception/satellite_rgb/**/*.py", recursive=True)
for file in sat_tests:
    with open(file, "r", encoding="utf-8") as f:
        content = f.read()
    if 'entry.get("filename", entry.get("file", ""))' in content or 'entry.get("filename", "")' in content:
        content = content.replace('os.path.join(os.path.dirname(__file__), entry.get("filename", entry.get("file", "")))', 
                                  'os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "common", "fixtures", "satellite", entry.get("filename", entry.get("file", "")))')
        content = content.replace('os.path.join(os.path.dirname(__file__), entry.get("filename", ""))', 
                                  'os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "common", "fixtures", "satellite", entry.get("filename", ""))')
        with open(file, "w", encoding="utf-8") as f:
            f.write(content)

# For farmer_photo tests
fp_tests = glob.glob("c:/Users/E-C/Desktop/agriwise/services/agribrain/layer0/perception/farmer_photo/**/*.py", recursive=True)
for file in fp_tests:
    with open(file, "r", encoding="utf-8") as f:
        content = f.read()
    if 'entry.get("filename", entry.get("file", ""))' in content or 'entry.get("filename", "")' in content:
        content = content.replace('os.path.join(os.path.dirname(__file__), entry.get("filename", entry.get("file", "")))', 
                                  'os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "common", "fixtures", "farmer_photo", entry.get("filename", entry.get("file", "")))')
        content = content.replace('os.path.join(os.path.dirname(__file__), entry.get("filename", ""))', 
                                  'os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "common", "fixtures", "farmer_photo", entry.get("filename", ""))')
        with open(file, "w", encoding="utf-8") as f:
            f.write(content)
print("Done fixing fixture paths!")
