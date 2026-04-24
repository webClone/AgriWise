import subprocess
try:
    with open("capture_out.txt", "w", encoding="utf-8") as f:
        result = subprocess.run(["C:\\Users\\E-C\\AppData\\Local\\Programs\\Python\\Python315\\python.exe", "debug_chat.py"], capture_output=True, text=True)
        f.write("=== STDOUT ===\n")
        f.write(result.stdout)
        f.write("\n=== STDERR ===\n")
        f.write(result.stderr)
        f.write("\n=== EXIT CODE ===\n")
        f.write(str(result.returncode))
except Exception as e:
    print(e)
