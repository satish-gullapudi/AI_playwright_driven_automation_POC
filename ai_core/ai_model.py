import google.generativeai as genai
import os


# Pick the first "gemini" model that includes "flash" and is not a preview
def get_latest_gemini_model():
    genai.configure(api_key=os.getenv("API_KEY"))
    models = [m.name for m in genai.list_models()]
    for preferred in ["gemini-2.5-flash", "gemini-flash-latest", "gemini-2.0-flash"]:
        if any(preferred in m for m in models):
            return preferred
    # fallback to any available gemini model
    for m in models:
        if "gemini" in m and "flash" in m:
            return m
    raise RuntimeError("No Gemini models found in your account!")

GEMINI_MODEL = genai.GenerativeModel(get_latest_gemini_model())
print(f"[INFO] Using model: {GEMINI_MODEL.model_name}")
