import importlib, sys, traceback

def check(name):
    try:
        mod = importlib.import_module(name)
        print(f"IMPORT_OK: {name}")
        # show a few useful attributes if present
        for attr in ("generate", "responses", "Client", "chat", "configure"):
            print(f"  has_{attr} =", hasattr(mod, attr))
    except Exception as e:
        print(f"IMPORT_FAIL: {name} -> {e.__class__.__name__}: {e}")

names = [
    "google.generativeai",
    "google_genai",
    "google.genai",
    "genai",
    "generativeai",
]

print("Python:", sys.executable)
for n in names:
    check(n)

# quick runtime test for gemini key visibility
import os
print("GEMINI_API_KEY present:", bool(os.getenv("GEMINI_API_KEY")))