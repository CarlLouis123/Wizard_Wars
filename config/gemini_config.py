import os
from pathlib import Path
MODEL_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent"
def get_api_key():
    k = os.getenv("GOOGLE_API_KEY")
    if k: return k.strip()
    p = Path(__file__).with_name("api_key.txt")
    return p.read_text(encoding="utf-8").strip() if p.exists() else None
