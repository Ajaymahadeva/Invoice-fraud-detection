from dotenv import load_dotenv
import os, importlib, json, sys, traceback

load_dotenv()  # ensure .env loaded
print("GEMINI_API_KEY present:", bool(os.getenv("GEMINI_API_KEY")))

try:
    genai = importlib.import_module("genai")
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    print("genai module:", genai, "client created")
    resp = client.generate(model="gemini-2.5-flash", prompt="Say hello", max_output_tokens=64)
    # try common extraction patterns
    text = getattr(resp, "text", None)
    if not text:
        try:
            text = resp.output[0].content[0].text
        except Exception:
            text = str(resp)
    print("Response text:", text)
except Exception:
    print("GenAI test failed:")
    traceback.print_exc()
    sys.exit(1)