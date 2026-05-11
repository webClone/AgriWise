import re

path = 'app/main.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace any character that is a surrogate
clean = "".join(c for c in content if not (0xD800 <= ord(c) <= 0xDFFF))

with open(path, 'w', encoding='utf-8') as f:
    f.write(clean)

print("Fixed surrogates")
